"""
Test: Idempotency — same order event sent twice must only decrement stock once.

This is critical for Shopify webhook retries. If Shopify doesn't get a 200
within 5 seconds, it retries the webhook. Without idempotency, the same order
would decrement inventory twice — causing stock to go negative.

How it works:
1. Record stock before test
2. Fire the same webhook twice with identical order ID
3. Assert stock decremented exactly once
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import requests
import time
import uuid
from database.session import SessionLocal
from database.models import Product, Inventory, Channel
from dotenv import load_dotenv

load_dotenv()

API_BASE = "http://localhost:8000"


def get_stock(sku: str, channel_name: str) -> int:
    """Helper — reads current stock for a SKU+channel from Postgres directly."""
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


def test_duplicate_webhook_decrements_once():
    """
    Fire the same Shopify order twice.
    Stock must decrement by exactly 1, not 2.
    """
    sku = "CHARGER-CABLE-6FT"
    channel = "shopify"
    order_id = random_order_id = f"TEST-IDEM-{uuid.uuid4().hex[:8].upper()}"
    qty = 1

    # Record stock before
    stock_before = get_stock(sku, channel)
    assert stock_before > 0, f"Need stock > 0 for test. {sku} on {channel} has {stock_before}"

    payload = {
        "id": order_id,
        "line_items": [{"sku": sku, "quantity": qty}]
    }

    # Fire webhook once
    r1 = requests.post(f"{API_BASE}/webhooks/shopify", json=payload)
    assert r1.status_code == 200, f"First webhook failed: {r1.text}"

    # Wait for sync consumer to process
    time.sleep(3)

    # Fire exact same webhook again — simulating Shopify retry
    r2 = requests.post(f"{API_BASE}/webhooks/shopify", json=payload)
    assert r2.status_code == 200, f"Second webhook failed: {r2.text}"

    # Wait for any processing
    time.sleep(3)

    stock_after = get_stock(sku, channel)

    # Stock should have decreased by exactly qty — not 2*qty
    expected = stock_before - qty
    assert stock_after == expected, (
        f"Idempotency FAILED: stock went from {stock_before} to {stock_after}. "
        f"Expected {expected} (decremented once). "
        f"Duplicate webhook was processed twice."
    )
    print(f"\n✅ Idempotency passed: {sku} on {channel}: {stock_before} → {stock_after} (decremented once)")