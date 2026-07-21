from fastapi import APIRouter, HTTPException, Request
from confluent_kafka import Producer
import json
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# ---------------------------------------------------------------------------
# Kafka Producer — one instance reused across all webhook requests
# bootstrap.servers tells the producer where Kafka is running
# ---------------------------------------------------------------------------
producer = Producer({
    "bootstrap.servers": os.getenv("KAFKA_BROKER", "localhost:9092")
})


def delivery_report(err, msg):
    """
    Callback fired by Kafka after every message is delivered (or fails).
    Kafka delivery is async — this callback tells you what happened.
    err is None on success, an Exception on failure.
    """
    if err is not None:
        print(f"  Delivery FAILED: {err}")
    else:
        print(f"  Delivered to {msg.topic()} partition [{msg.partition()}] offset {msg.offset()}")


@router.post("/shopify")
async def shopify_webhook(request: Request):
    """
    Receives order webhook from Shopify (or mock Shopify server).

    Why return 200 immediately without waiting for inventory update:
    Shopify marks a webhook as failed if it doesn't get 200 within 5 seconds.
    Inventory processing happens asynchronously in the Kafka consumer.
    We never make Shopify wait for our database.
    """
    payload = await request.json()

    # Build the idempotency key — unique per order per channel
    # If Shopify retries this webhook, we get the same key and skip processing
    order_id = payload.get("id", str(uuid.uuid4()))
    idempotency_key = f"shopify_{order_id}_v1"

    # Build the Kafka event
    event = {
        "event_id": str(uuid.uuid4()),
        "idempotency_key": idempotency_key,
        "channel": "shopify",
        "event_type": "order.created",
        "payload": payload
    }

    # Publish to Kafka — non-blocking
    # The producer queues the message and returns immediately
    # delivery_report callback fires when Kafka confirms receipt
    producer.produce(
        topic="order-events",
        key=idempotency_key,           # partition key — same order always goes to same partition
        value=json.dumps(event),
        callback=delivery_report
    )
    producer.poll(0)  # trigger delivery callbacks without blocking

    from services.api.metrics import WEBHOOK_EVENTS, KAFKA_MESSAGES_PRODUCED
    WEBHOOK_EVENTS.labels(channel="shopify", event_type="order.created").inc()
    KAFKA_MESSAGES_PRODUCED.labels(topic="order-events").inc()    

    return {
        "status": "received",
        "event_id": event["event_id"],
        "idempotency_key": idempotency_key
    }


@router.post("/amazon")
async def amazon_webhook(request: Request):
    """
    Receives order webhook from Amazon SP-API (or mock Amazon server).
    Amazon uses AmazonOrderId, OrderItems instead of Shopify's id, line_items.
    We normalize to the same internal event format before publishing to Kafka.
    """
    payload = await request.json()

    order_id = payload.get("AmazonOrderId", str(uuid.uuid4()))
    idempotency_key = f"amazon_{order_id}_v1"

    # Normalize Amazon line items to match our internal format
    # Amazon uses SellerSKU and QuantityOrdered
    # Our consumer expects sku and quantity
    order_items = payload.get("OrderItems", [])
    normalized_items = [
        {
            "sku": item.get("SellerSKU"),
            "quantity": item.get("QuantityOrdered", 1),
            "unit_price": float(item.get("ItemPrice", {}).get("Amount", 0)) / max(item.get("QuantityOrdered", 1), 1)
        }
        for item in order_items
        if item.get("SellerSKU") and item.get("QuantityOrdered", 0) > 0
    ]

    # Build normalized event — same format as Shopify
    event = {
        "event_id": str(uuid.uuid4()),
        "idempotency_key": idempotency_key,
        "channel": "amazon",
        "event_type": "order.created",
        "payload": {
            "id": order_id,
            "line_items": normalized_items,
            "raw": payload  # preserve original for audit
        }
    }

    producer.produce(
        topic="order-events",
        key=idempotency_key,
        value=json.dumps(event),
        callback=delivery_report
    )
    producer.poll(0)

    from services.api.metrics import WEBHOOK_EVENTS, KAFKA_MESSAGES_PRODUCED
    WEBHOOK_EVENTS.labels(channel="amazon", event_type="order.created").inc()
    KAFKA_MESSAGES_PRODUCED.labels(topic="order-events").inc()

    return {
        "status": "received",
        "event_id": event["event_id"],
        "idempotency_key": idempotency_key
    }