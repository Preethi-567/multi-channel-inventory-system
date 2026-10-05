import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from database.session import SessionLocal
from database.models import Product, Channel, Order, OrderItem, InventoryLedger
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import random
import uuid

load_dotenv()

# Daily units sold on Shopify — realistic for Indian SMB
DAILY_VELOCITY = {
    # Electronics
    "EARBUDS-BLK":        2.5,
    "EARBUDS-WHT":        2.2,
    "DESK-LAMP-WHT":      1.8,
    "POWERBANK-10K":      3.0,
    "SPKR-BT-BLK":        1.5,
    "HEADPHONE-ANC-BLK":  0.8,
    "WEBCAM-1080P":        1.0,
    "MOUSE-WIRELESS-GRY": 3.5,
    "KEYBOARD-MECH-RGB":  0.7,
    "USB-HUB-7PORT":      2.8,
    # Fitness & Kitchen
    "WATERBOTTLE-1L":     5.0,
    "MUG-CERAMIC-BLK":    6.0,
    "CUTTINGBOARD-WD":    3.5,
    "CHEF-KNIFE-8IN":     2.0,
    "LUNCHBOX-STL":       4.5,
    "YOGA-MAT-PUR":       2.5,
    "DUMBBELL-5KG-PAIR":  1.5,
    "RES-BAND-SET":       4.0,
    "SHAKER-BOTTLE-750":  4.5,
    "FOAM-ROLLER-BLK":    2.0,
    # Accessories
    "PHONE-CASE-S23":     7.0,
    "CHARGER-CABLE-6FT":  8.0,
    "WATCH-STRAP-BLK":    4.5,
    "SUNGLASSES-POL-BLK": 3.0,
    "WALLET-LEATHER-BRN": 2.5,
    # Handmade Crafts — lower velocity, artisan products
    "MADHUBANI-PAINT":    0.4,
    "BRASS-GANESHA":      0.8,
    "JUTE-BASKET":        1.5,
    "BLOCKPRINT-KURTA":   1.0,
    "COPPER-BOTTLE":      1.8,
    "TERRACOTTA-POT":     1.5,
    "SANDALWOOD-INCENSE": 3.5,
    "EMBROIDERED-CUSHION":1.2,
    "WARLI-FRAME":        0.3,
    "BAMBOO-TRAY":        1.5,
}

AMAZON_MULTIPLIER = 0.6

DOW_MULTIPLIER = {
    0: 0.8, 1: 0.9, 2: 1.0, 3: 1.0,
    4: 1.3, 5: 1.5, 6: 1.4,
}

MONTH_MULTIPLIER = {
    1: 0.8, 2: 0.8, 3: 0.9, 4: 0.9,
    5: 1.0, 6: 1.0, 7: 1.0, 8: 1.0,
    9: 1.1, 10: 1.8,  # Diwali
    11: 1.3, 12: 1.4,
}

# Handmade crafts spike during Diwali and gifting seasons
CRAFT_MONTH_MULTIPLIER = {
    1: 0.7, 2: 0.7, 3: 0.8, 4: 0.8,
    5: 0.9, 6: 0.9, 7: 0.9, 8: 1.0,
    9: 1.2, 10: 2.5,  # Diwali gifts — bigger spike for crafts
    11: 1.8, 12: 1.6,
}

CRAFT_SKUS = {
    "MADHUBANI-PAINT", "BRASS-GANESHA", "JUTE-BASKET",
    "BLOCKPRINT-KURTA", "COPPER-BOTTLE", "TERRACOTTA-POT",
    "SANDALWOOD-INCENSE", "EMBROIDERED-CUSHION", "WARLI-FRAME", "BAMBOO-TRAY"
}


def get_daily_demand(sku: str, date: datetime, channel: str) -> int:
    base = DAILY_VELOCITY.get(sku, 1.0)
    if channel == "amazon":
        base *= AMAZON_MULTIPLIER

    dow_mult = DOW_MULTIPLIER[date.weekday()]

    if sku in CRAFT_SKUS:
        month_mult = CRAFT_MONTH_MULTIPLIER[date.month]
    else:
        month_mult = MONTH_MULTIPLIER[date.month]

    mean = base * dow_mult * month_mult
    return max(0, int(random.gauss(mean, mean * 0.3)))


def generate_historical_sales(months_back: int = 6):
    db = SessionLocal()
    try:
        products = {p.sku: p for p in db.query(Product).all()}
        channels = {c.name: c for c in db.query(Channel).all()}

        if not products or not channels:
            print("No products or channels found — run seed_initial_data.py first")
            return

        end_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=months_back * 30)

        print(f"Generating {months_back} months of sales history")
        print(f"  From: {start_date.date()} → {end_date.date()}")
        print(f"  Products: {len(products)} | Channels: {len(channels)}")

        total_orders = 0
        total_units = 0
        current_date = start_date

        while current_date < end_date:
            for channel_name, channel in channels.items():
                daily_orders = random.randint(3, 8)
                for _ in range(daily_orders):
                    num_items = random.randint(1, 3)
                    selected_skus = random.sample(list(products.keys()), num_items)

                    line_items = []
                    for sku in selected_skus:
                        qty = get_daily_demand(sku, current_date, channel_name)
                        if qty > 0:
                            line_items.append((sku, qty))

                    if not line_items:
                        continue

                    order_time = current_date + timedelta(
                        hours=random.randint(9, 21),
                        minutes=random.randint(0, 59)
                    )
                    external_id = f"HIST-{channel_name[:3].upper()}-{uuid.uuid4().hex[:8].upper()}"

                    order = Order(
                        id=uuid.uuid4(),
                        external_id=external_id,
                        channel_id=channel.id,
                        idempotency_key=f"{channel_name}_{external_id}_v1",
                        status="processed",
                        raw_payload={"historical": True, "date": str(current_date.date())},
                        created_at=order_time,
                        processed_at=order_time,
                    )
                    db.add(order)
                    db.flush()

                    for sku, qty in line_items:
                        product = products[sku]
                        db.add(OrderItem(
                            id=uuid.uuid4(),
                            order_id=order.id,
                            product_id=product.id,
                            sku=sku,
                            quantity=qty,
                            unit_price=product.selling_price,
                        ))
                        db.add(InventoryLedger(
                            id=uuid.uuid4(),
                            product_id=product.id,
                            channel_id=channel.id,
                            change_type="sale",
                            quantity_delta=-qty,
                            quantity_after=0,
                            reference_id=order.id,
                            notes=f"Historical sale {current_date.date()}",
                            created_at=order_time,
                        ))
                        total_units += qty
                    total_orders += 1

            db.commit()
            current_date += timedelta(days=1)
            if current_date.day == 1:
                print(f"  Progress: {current_date.date()} — {total_orders} orders")

        print(f"\nDone! {total_orders} orders, {total_units} units")

    except Exception as e:
        db.rollback()
        print(f"FAILED: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    generate_historical_sales(months_back=6)