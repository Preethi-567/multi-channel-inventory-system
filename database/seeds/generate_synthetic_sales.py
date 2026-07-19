import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from database.session import SessionLocal
from database.models import Product, Channel, Order, OrderItem, InventoryLedger, Inventory
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import random
import uuid

load_dotenv()

# ---------------------------------------------------------------------------
# Indian SMB sales patterns
# ---------------------------------------------------------------------------

# How many units of each SKU sell per day on average (shopify)
DAILY_VELOCITY = {
    "TSHIRT-RED-M":   3.5,
    "TSHIRT-BLU-L":   3.0,
    "EARBUDS-BLK":    1.5,
    "EARBUDS-WHT":    1.2,
    "WATERBOTTLE-1L": 4.0,
    "BACKPACK-BLK":   1.0,
    "PHONE-CASE-S23": 6.0,
    "YOGA-MAT-PUR":   1.8,
    "DESK-LAMP-WHT":  1.2,
    "NOTEBOOK-A5":    8.0,
}

# Amazon sells at 60% of Shopify velocity
AMAZON_MULTIPLIER = 0.6

# Day-of-week multipliers (0=Monday, 6=Sunday)
DOW_MULTIPLIER = {
    0: 0.8,   # Monday — slow
    1: 0.9,   # Tuesday
    2: 1.0,   # Wednesday
    3: 1.0,   # Thursday
    4: 1.3,   # Friday — payday spike
    5: 1.5,   # Saturday — peak
    6: 1.4,   # Sunday — high
}

# Monthly multipliers — Diwali in October, year-end in December
MONTH_MULTIPLIER = {
    1: 0.8, 2: 0.8, 3: 0.9, 4: 0.9,
    5: 1.0, 6: 1.0, 7: 1.0, 8: 1.0,
    9: 1.1, 10: 1.8,  # Diwali spike
    11: 1.3, 12: 1.4,
}


def get_daily_demand(sku: str, date: datetime, channel: str) -> int:
    """
    Generates realistic daily demand for a SKU on a given date and channel.
    Combines base velocity with day-of-week and monthly seasonality.
    Adds random noise to simulate real-world variation.
    """
    base = DAILY_VELOCITY.get(sku, 1.0)
    if channel == "amazon":
        base *= AMAZON_MULTIPLIER

    dow_mult = DOW_MULTIPLIER[date.weekday()]
    month_mult = MONTH_MULTIPLIER[date.month]

    # Poisson-like noise — sales are random but cluster around the mean
    mean = base * dow_mult * month_mult
    demand = max(0, int(random.gauss(mean, mean * 0.3)))
    return demand


def generate_historical_sales(months_back: int = 6):
    """
    Generates synthetic historical sales data for the past N months.
    Writes directly to orders, order_items, and inventory_ledger tables.
    Does NOT touch current inventory counts — historical only.
    """
    db = SessionLocal()
    try:
        # Load all products and channels
        products = {p.sku: p for p in db.query(Product).all()}
        channels = {c.name: c for c in db.query(Channel).all()}

        if not products or not channels:
            print("No products or channels found — run seed_initial_data.py first")
            return

        end_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start_date = end_date - timedelta(days=months_back * 30)

        print(f"Generating sales from {start_date.date()} to {end_date.date()}")
        print(f"Products: {len(products)}, Channels: {len(channels)}")

        total_orders = 0
        total_units = 0
        current_date = start_date

        while current_date < end_date:
            # Generate 3-8 orders per day per channel
            for channel_name, channel in channels.items():
                daily_orders = random.randint(3, 8)

                for _ in range(daily_orders):
                    # Each order has 1-3 line items
                    num_items = random.randint(1, 3)
                    selected_skus = random.sample(list(products.keys()), num_items)

                    line_items = []
                    for sku in selected_skus:
                        qty = get_daily_demand(sku, current_date, channel_name)
                        if qty > 0:
                            line_items.append((sku, qty))

                    if not line_items:
                        continue

                    # Random time during business hours
                    order_time = current_date + timedelta(
                        hours=random.randint(9, 21),
                        minutes=random.randint(0, 59)
                    )

                    # Create order
                    external_id = f"HIST-{channel_name[:3].upper()}-{random.randint(100000, 999999)}"
                    idempotency_key = f"{channel_name}_{external_id}_v1"

                    order = Order(
                        id=uuid.uuid4(),
                        external_id=external_id,
                        channel_id=channel.id,
                        idempotency_key=idempotency_key,
                        status="processed",
                        raw_payload={"historical": True, "date": str(current_date.date())},
                        created_at=order_time,
                        processed_at=order_time,
                    )
                    db.add(order)
                    db.flush()

                    for sku, qty in line_items:
                        product = products[sku]

                        # Order item
                        order_item = OrderItem(
                            id=uuid.uuid4(),
                            order_id=order.id,
                            product_id=product.id,
                            sku=sku,
                            quantity=qty,
                            unit_price=product.selling_price,
                        )
                        db.add(order_item)

                        # Ledger entry — historical record only
                        ledger = InventoryLedger(
                            id=uuid.uuid4(),
                            product_id=product.id,
                            channel_id=channel.id,
                            change_type="sale",
                            quantity_delta=-qty,
                            quantity_after=0,  # historical — not tracking running total
                            reference_id=order.id,
                            notes=f"Historical sale {current_date.date()}",
                            created_at=order_time,
                        )
                        db.add(ledger)
                        total_units += qty

                    total_orders += 1

            # Commit every day to avoid huge transactions
            db.commit()
            current_date += timedelta(days=1)

            if current_date.day == 1:
                print(f"  Progress: {current_date.date()} — {total_orders} orders so far")

        print(f"\nDone!")
        print(f"  Total orders: {total_orders}")
        print(f"  Total units sold: {total_units}")
        print(f"  Date range: {start_date.date()} → {end_date.date()}")

    except Exception as e:
        db.rollback()
        print(f"FAILED: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    generate_historical_sales(months_back=6)