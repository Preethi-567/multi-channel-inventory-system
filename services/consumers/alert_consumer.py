import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from confluent_kafka import Consumer, KafkaError
from database.session import SessionLocal
from database.models import Alert, Inventory, Product, Channel
from dotenv import load_dotenv
import json
import uuid
from datetime import datetime, timezone

load_dotenv()

consumer = Consumer({
    "bootstrap.servers": os.getenv("KAFKA_BROKER", "localhost:9092"),
    "group.id": "alert-consumer-group",  # separate group from sync consumer
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,
})


def check_and_create_alerts(product_id: str, channel_id: str, db):
    """
    Checks current stock against reorder_point.
    Creates an alert if stock is at or below reorder_point.
    Skips if an unread alert already exists for this SKU+channel.
    """
    inventory = db.query(Inventory).filter(
        Inventory.product_id == product_id,
        Inventory.channel_id == channel_id
    ).first()

    if not inventory:
        return

    product = db.query(Product).filter(Product.id == product_id).first()
    channel = db.query(Channel).filter(Channel.id == channel_id).first()

    if not product or not channel:
        return

    stock = inventory.quantity_on_hand
    reorder_point = product.reorder_point

    # Determine alert type and severity
    if stock == 0:
        alert_type = "stockout"
        severity = "critical"
        message = (
            f"STOCKOUT: {product.sku} on {channel.name} — "
            f"0 units remaining. Reorder immediately. "
            f"Lead time: {product.supplier_lead_days} days."
        )
    elif stock <= reorder_point // 2:
        alert_type = "low_stock_critical"
        severity = "critical"
        message = (
            f"CRITICAL LOW STOCK: {product.sku} on {channel.name} — "
            f"{stock} units (reorder point: {reorder_point}). "
            f"Reorder qty: {product.reorder_qty}."
        )
    elif stock <= reorder_point:
        alert_type = "low_stock"
        severity = "warning"
        message = (
            f"LOW STOCK: {product.sku} on {channel.name} — "
            f"{stock} units (reorder point: {reorder_point}). "
            f"Consider reordering {product.reorder_qty} units."
        )
    else:
        # Stock is fine — no alert needed
        return

    # Check if an unread alert already exists for this SKU+channel+type
    # Prevents alert spam — one active alert per SKU per channel
    existing = db.query(Alert).filter(
        Alert.product_id == product_id,
        Alert.channel_id == channel_id,
        Alert.alert_type == alert_type,
        Alert.is_read == False
    ).first()

    if existing:
        print(f"  Alert already exists for {product.sku} on {channel.name} — skipping")
        return

    # Create the alert
    alert = Alert(
        id=uuid.uuid4(),
        product_id=product_id,
        channel_id=channel_id,
        alert_type=alert_type,
        message=message,
        severity=severity,
        is_read=False,
    )
    db.add(alert)
    db.commit()

    # Print alert — in production this fires a Twilio WhatsApp message
    severity_prefix = "🔴" if severity == "critical" else "🟡"
    print(f"  {severity_prefix} ALERT [{severity.upper()}]: {message}")


def process_inventory_update(event: dict, db):
    """
    Processes an inventory-updates event.
    Each event carries product_id and channel_id of what changed.
    """
    product_id = event.get("product_id")
    channel_id = event.get("channel_id")

    if not product_id or not channel_id:
        print(f"  Missing product_id or channel_id in event — skipping")
        return

    check_and_create_alerts(product_id, channel_id, db)


def run():
    consumer.subscribe(["inventory-updates"])
    print("Alert consumer started — listening on inventory-updates...")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"Consumer error: {msg.error()}")
                continue

            try:
                event = json.loads(msg.value().decode("utf-8"))
                print(f"Checking inventory for: {event.get('product_id', 'unknown')[:8]}...")
            except json.JSONDecodeError as e:
                print(f"Bad JSON: {e}")
                consumer.commit(message=msg)
                continue

            db = SessionLocal()
            try:
                process_inventory_update(event, db)
            except Exception as e:
                db.rollback()
                print(f"  Error: {e}")
            finally:
                db.close()

            consumer.commit(message=msg)

    except KeyboardInterrupt:
        print("\nShutting down alert consumer...")
    finally:
        consumer.close()


if __name__ == "__main__":
    run()