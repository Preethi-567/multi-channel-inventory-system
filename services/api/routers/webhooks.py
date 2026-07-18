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

    return {
        "status": "received",
        "event_id": event["event_id"],
        "idempotency_key": idempotency_key
    }


@router.post("/amazon")
async def amazon_webhook(request: Request):
    """
    Same pattern as Shopify — different channel name and idempotency key prefix.
    """
    payload = await request.json()

    order_id = payload.get("AmazonOrderId", str(uuid.uuid4()))
    idempotency_key = f"amazon_{order_id}_v1"

    event = {
        "event_id": str(uuid.uuid4()),
        "idempotency_key": idempotency_key,
        "channel": "amazon",
        "event_type": "order.created",
        "payload": payload
    }

    producer.produce(
        topic="order-events",
        key=idempotency_key,
        value=json.dumps(event),
        callback=delivery_report
    )
    producer.poll(0)

    return {
        "status": "received",
        "event_id": event["event_id"],
        "idempotency_key": idempotency_key
    }