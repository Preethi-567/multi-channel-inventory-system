import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from confluent_kafka import Consumer, KafkaError, Producer
from database.session import SessionLocal
from database.models import Order, OrderItem, Inventory, InventoryLedger, Product, Channel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from dotenv import load_dotenv
import json
import uuid
from datetime import datetime, timezone

load_dotenv()

# ---------------------------------------------------------------------------
# Kafka Consumer — reads from order-events topic
# group.id identifies this consumer group — Kafka tracks its offset separately
# auto.offset.reset = earliest means: on first run, read from the beginning
# enable.auto.commit = false means: WE commit offsets manually, AFTER
#   successful DB write. Never before. This is at-least-once delivery.
# ---------------------------------------------------------------------------
consumer = Consumer({
    "bootstrap.servers": os.getenv("KAFKA_BROKER", "localhost:9092"),
    "group.id": "sync-consumer-group",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,
})

# Producer for dead-letter-queue — failed events go here
dlq_producer = Producer({
    "bootstrap.servers": os.getenv("KAFKA_BROKER", "localhost:9092"),
})

MAX_RETRIES = 5


def send_to_dlq(event: dict, reason: str):
    """
    Sends a failed event to the dead-letter-queue topic.
    Never silently discard a failed event — always park it in DLQ.
    """
    dlq_event = {
        "original_event": event,
        "failure_reason": reason,
        "failed_at": datetime.now(timezone.utc).isoformat()
    }
    dlq_producer.produce(
        topic="dead-letter-queue",
        value=json.dumps(dlq_event)
    )
    dlq_producer.poll(0)
    print(f"  Sent to DLQ: {reason}")


def process_order(event: dict, db: Session) -> bool:
    """
    Core processing logic for a single order event.
    Returns True if processed successfully, False if should go to DLQ.

    Steps:
    1. Check idempotency key — skip if already processed
    2. Create Order record
    3. For each line item — decrement inventory with optimistic locking
    4. Write to inventory_ledger
    5. Commit everything atomically
    """
    idempotency_key = event.get("idempotency_key")
    channel_name = event.get("channel")
    payload = event.get("payload", {})

    # ── Step 1: Idempotency check ────────────────────────────────────────────
    # If this key exists, this is a duplicate webhook retry — skip silently
    existing_order = db.query(Order).filter(
        Order.idempotency_key == idempotency_key
    ).first()

    if existing_order:
        print(f"  Duplicate detected — skipping: {idempotency_key}")
        return True  # not an error — intentional skip

    # ── Step 2: Find the channel ─────────────────────────────────────────────
    channel = db.query(Channel).filter(Channel.name == channel_name).first()
    if not channel:
        print(f"  Unknown channel: {channel_name}")
        return False

    # ── Step 3: Create Order record ──────────────────────────────────────────
    order = Order(
        id=uuid.uuid4(),
        external_id=str(payload.get("id", uuid.uuid4())),
        channel_id=channel.id,
        idempotency_key=idempotency_key,
        status="processing",
        raw_payload=payload,
    )
    db.add(order)
    db.flush()  # get order.id without committing yet

    # ── Step 4: Process each line item ───────────────────────────────────────
    line_items = payload.get("line_items", [])
    if not line_items:
        print(f"  No line items in order — skipping")
        return False

    for item in line_items:
        sku = item.get("sku")
        quantity = item.get("quantity", 0)

        if not sku or quantity <= 0:
            continue

        # Find the product
        product = db.query(Product).filter(Product.sku == sku).first()
        if not product:
            print(f"  SKU not found: {sku} — sending to DLQ")
            return False

        # Find inventory for this product+channel
        inventory = db.query(Inventory).filter(
            Inventory.product_id == product.id,
            Inventory.channel_id == channel.id
        ).first()

        if not inventory:
            print(f"  No inventory record for {sku} on {channel_name}")
            return False

        # ── Optimistic locking loop ──────────────────────────────────────────
        # Read current version, update with version check
        # If someone else updated between our read and write, retry
        success = False
        for attempt in range(MAX_RETRIES):
            current_version = inventory.version
            current_stock = inventory.quantity_on_hand

            if current_stock < quantity:
                print(f"  Insufficient stock for {sku}: has {current_stock}, needs {quantity}")
                return False

            # Conditional UPDATE — only succeeds if version hasn't changed
            rows_updated = db.query(Inventory).filter(
                Inventory.id == inventory.id,
                Inventory.version == current_version
            ).update({
                "quantity_on_hand": current_stock - quantity,
                "version": current_version + 1,
                "updated_at": datetime.now(timezone.utc)
            })

            if rows_updated == 1:
                # Success — write ledger entry
                ledger = InventoryLedger(
                    id=uuid.uuid4(),
                    product_id=product.id,
                    channel_id=channel.id,
                    change_type="sale",
                    quantity_delta=-quantity,
                    quantity_after=current_stock - quantity,
                    reference_id=order.id,
                    notes=f"Order {idempotency_key}"
                )
                db.add(ledger)

                # Add order item
                order_item = OrderItem(
                    id=uuid.uuid4(),
                    order_id=order.id,
                    product_id=product.id,
                    sku=sku,
                    quantity=quantity,
                    unit_price=item.get("unit_price", product.selling_price)
                )
                db.add(order_item)

                print(f"  {sku}: {current_stock} → {current_stock - quantity} (attempt {attempt + 1})")
                success = True
                break
            else:
                # Conflict — someone else updated — refresh and retry
                print(f"  Version conflict on {sku} — retrying (attempt {attempt + 1})")
                db.refresh(inventory)

        if not success:
            print(f"  Max retries exceeded for {sku}")
            return False

    # ── Step 5: Mark order as processed and commit ───────────────────────────
    order.status = "processed"
    order.processed_at = datetime.now(timezone.utc)
    db.commit()
    print(f"  Order committed: {idempotency_key}")
    return True


def run():
    """
    Main consumer loop — runs forever, polling Kafka for new messages.
    """
    consumer.subscribe(["order-events"])
    print("Sync consumer started — listening on order-events...")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            # Poll for a message — wait up to 1 second
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue  # no message — keep polling

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue  # end of partition — normal, keep polling
                print(f"Consumer error: {msg.error()}")
                continue

            # Parse the event
            try:
                event = json.loads(msg.value().decode("utf-8"))
                print(f"Processing: {event.get('idempotency_key')}")
            except json.JSONDecodeError as e:
                print(f"Bad JSON — sending to DLQ: {e}")
                send_to_dlq({"raw": msg.value().decode("utf-8")}, str(e))
                consumer.commit(message=msg)
                continue

            # Process with a fresh DB session per message
            db = SessionLocal()
            try:
                success = process_order(event, db)
                if not success:
                    send_to_dlq(event, "Processing failed")
            except IntegrityError as e:
                # UNIQUE constraint violation on idempotency_key
                # This is a race condition between two consumer instances
                # processing the same message — safe to skip
                db.rollback()
                print(f"  IntegrityError (duplicate) — skipping: {e.orig}")
            except Exception as e:
                db.rollback()
                print(f"  Unexpected error — sending to DLQ: {e}")
                send_to_dlq(event, str(e))
            finally:
                db.close()

            # Commit offset AFTER successful processing
            # This is the at-least-once delivery guarantee:
            # if we crash before this line, Kafka replays the message
            consumer.commit(message=msg)

    except KeyboardInterrupt:
        print("\nShutting down consumer...")
    finally:
        consumer.close()


if __name__ == "__main__":
    run()