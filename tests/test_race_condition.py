"""
Test: Race condition safety — 10 concurrent orders must not cause negative inventory.

Without optimistic locking, two threads could both read stock=5, both think
they can fulfil an order for 1 unit, and both write stock=4. Final stock = 4
instead of 3. Under higher concurrency, stock goes negative.

This test fires 10 concurrent orders for 1 unit each against a SKU with
known stock. Final stock must be exactly (initial - fulfilled_orders) and
never negative.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import requests
import uuid
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from database.session import SessionLocal
from database.models import Product, Inventory, Channel
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


def fire_order(sku: str, qty: int) -> int:
    """Fires a single webhook and returns the HTTP status code."""
    payload = {
        "id": f"TEST-RACE-{uuid.uuid4().hex[:8].upper()}",
        "line_items": [{"sku": sku, "quantity": qty}]
    }
    try:
        r = requests.post(f"{API_BASE}/webhooks/shopify", json=payload, timeout=10)
        return r.status_code
    except Exception as e:
        print(f"Request failed: {e}")
        return 500


def test_concurrent_orders_no_negative_stock():
    """
    10 concurrent orders of 1 unit each.
    Final stock must be >= 0 and exactly (initial - successful_orders).
    """
    sku = "MOUSE-WIRELESS-GRY"
    channel = "shopify"
    concurrent_orders = 10
    qty_per_order = 1

    stock_before = get_stock(sku, channel)
    assert stock_before >= concurrent_orders, (
        f"Need at least {concurrent_orders} units for test. "
        f"{sku} on {channel} has {stock_before}"
    )

    # Fire all orders simultaneously
    with ThreadPoolExecutor(max_workers=concurrent_orders) as executor:
        futures = [
            executor.submit(fire_order, sku, qty_per_order)
            for _ in range(concurrent_orders)
        ]
        results = [f.result() for f in as_completed(futures)]

    successful = results.count(200)
    print(f"\n  Orders fired: {concurrent_orders}")
    print(f"  Successful (200): {successful}")
    print(f"  Failed/conflict: {concurrent_orders - successful}")

    # Wait for all consumers to finish processing
    time.sleep(5)

    stock_after = get_stock(sku, channel)

    # Critical assertion — stock must never go negative
    assert stock_after >= 0, (
        f"Race condition DETECTED: stock went negative! "
        f"Before: {stock_before}, After: {stock_after}"
    )

    # Stock should have decreased by exactly the number of successful orders
    expected = stock_before - (successful * qty_per_order)
    assert stock_after == expected, (
        f"Stock mismatch: expected {expected}, got {stock_after}. "
        f"Before: {stock_before}, successful orders: {successful}"
    )

    print(f"\n✅ Race condition test passed: {sku} on {channel}: {stock_before} → {stock_after}")
    print(f"   No negative inventory. Optimistic locking worked correctly.")