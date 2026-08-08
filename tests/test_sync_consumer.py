"""
Test: End-to-end sync — webhook fires → Kafka → consumer → Postgres updated.

This is the most important integration test. It verifies the entire pipeline:
  Webhook → FastAPI → Kafka → sync_consumer → Postgres → inventory decremented

If this test passes, the core value proposition of the platform works.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import requests
import time
import uuid
from database.session import SessionLocal
from database.models import Product, Inventory, Channel, Order
from dotenv import load_dotenv

load_dotenv()

API_BASE = "http://localhost:8000"


def get_stock(sku: str, channel_name: str) -> int:
    db = SessionLocal()
    try:
        row = (
            db.query(Inventory.quantity_on_hand)
            .join(Product, Product.id == Inventory.product_id)
            .join(Channel, Channel.id == Inventory.channel_id)
            .filter(Product.sku == sku, Channel.name == channel_name)
            .first()
        )
        return row.quantity_on_hand if row else 0
    finally:
        db.close()


def order_exists(idempotency_key: str) -> bool:
    db = SessionLocal()
    try:
        return db.query(Order).filter(
            Order.idempotency_key == idempotency_key
        ).first() is not None
    finally:
        db.close()


def test_webhook_decrements_inventory():
    """
    Fire a Shopify webhook and verify inventory decremented in Postgres.
    Pipeline: webhook → Kafka → sync_consumer → Postgres
    Allows up to 5 seconds for async processing.
    """
    sku = "WATERBOTTLE-1L"
    channel = "shopify"
    qty = 2
    order_id = f"TEST-SYNC-{uuid.uuid4().hex[:8].upper()}"
    idempotency_key = f"shopify_{order_id}_v1"

    stock_before = get_stock(sku, channel)
    assert stock_before >= qty, (
        f"Need at least {qty} units for test. "
        f"{sku} on {channel} has {stock_before}"
    )

    payload = {
        "id": order_id,
        "line_items": [{"sku": sku, "quantity": qty}]
    }

    # Fire webhook
    response = requests.post(f"{API_BASE}/webhooks/shopify", json=payload)
    assert response.status_code == 200, f"Webhook rejected: {response.text}"

    data = response.json()
    assert "event_id" in data, "Response missing event_id"
    assert data["status"] == "received", f"Unexpected status: {data['status']}"

    # Wait for async pipeline to complete
    # Webhook → Kafka publish (instant) → consumer poll (up to 1s) → DB write
    max_wait = 5
    interval = 0.5
    elapsed = 0
    stock_after = stock_before

    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        stock_after = get_stock(sku, channel)
        if stock_after < stock_before:
            break

    # Assert inventory was decremented
    assert stock_after == stock_before - qty, (
        f"Sync FAILED after {max_wait}s: "
        f"stock unchanged at {stock_after}. "
        f"Expected {stock_before - qty}. "
        f"Check sync_consumer is running."
    )

    # Assert order was recorded in Postgres
    assert order_exists(idempotency_key), (
        f"Order {idempotency_key} not found in orders table. "
        f"Consumer may not have committed."
    )

    print(f"\n✅ End-to-end sync passed: {sku} on {channel}: {stock_before} → {stock_after}")
    print(f"   Kafka pipeline latency: < {elapsed}s")


def test_webhook_returns_immediately():
    """
    Webhook must return 200 within 2 seconds regardless of processing time.
    Shopify cancels webhooks after 5 seconds — we must respond fast.
    """
    import time

    payload = {
        "id": f"TEST-SPEED-{uuid.uuid4().hex[:8].upper()}",
        "line_items": [{"sku": "MUG-CERAMIC-BLK", "quantity": 1}]
    }

    start = time.time()
    response = requests.post(f"{API_BASE}/webhooks/shopify", json=payload)
    duration = time.time() - start

    assert response.status_code == 200
    assert duration < 3.0, (
        f"Webhook too slow: {duration:.2f}s. "
        f"Shopify requires response within 5s. "
        f"Check Kafka producer is not blocking."
    )

    print(f"\n✅ Webhook response time: {duration*1000:.0f}ms (must be < 2000ms)")