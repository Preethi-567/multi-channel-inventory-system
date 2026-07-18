import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from database.session import SessionLocal
from database.models import Product, Channel, Inventory
import uuid

def seed():
    db = SessionLocal()
    try:
        # ── Channels ────────────────────────────────────────────────────────
        # Check if already seeded — running this twice should be safe
        existing = db.query(Channel).first()
        if existing:
            print("Database already seeded — skipping.")
            return

        print("Seeding channels...")
        shopify = Channel(
            id=uuid.uuid4(),
            name="shopify",
            api_config={"webhook_url": "http://localhost:8001"},
            is_active=True
        )
        amazon = Channel(
            id=uuid.uuid4(),
            name="amazon",
            api_config={"webhook_url": "http://localhost:8002"},
            is_active=True
        )
        db.add_all([shopify, amazon])
        db.flush()  # write to DB but don't commit yet — we need the IDs below

        # ── Products ─────────────────────────────────────────────────────────
        print("Seeding products...")
        products = [
            Product(sku="TSHIRT-RED-M",   name="Classic Tee Red M",        category="Apparel",     unit_cost=150, selling_price=599,  reorder_point=20, reorder_qty=100, supplier_lead_days=7),
            Product(sku="TSHIRT-BLU-L",   name="Classic Tee Blue L",       category="Apparel",     unit_cost=150, selling_price=599,  reorder_point=20, reorder_qty=100, supplier_lead_days=7),
            Product(sku="EARBUDS-BLK",    name="Wireless Earbuds Black",   category="Electronics", unit_cost=800, selling_price=2499, reorder_point=15, reorder_qty=50,  supplier_lead_days=14),
            Product(sku="EARBUDS-WHT",    name="Wireless Earbuds White",   category="Electronics", unit_cost=800, selling_price=2499, reorder_point=15, reorder_qty=50,  supplier_lead_days=14),
            Product(sku="WATERBOTTLE-1L", name="Steel Water Bottle 1L",    category="Kitchen",     unit_cost=200, selling_price=799,  reorder_point=25, reorder_qty=150, supplier_lead_days=5),
            Product(sku="BACKPACK-BLK",   name="Laptop Backpack Black",    category="Bags",        unit_cost=600, selling_price=1999, reorder_point=10, reorder_qty=60,  supplier_lead_days=10),
            Product(sku="PHONE-CASE-S23", name="Phone Case Samsung S23",   category="Accessories", unit_cost=80,  selling_price=349,  reorder_point=30, reorder_qty=200, supplier_lead_days=5),
            Product(sku="YOGA-MAT-PUR",   name="Yoga Mat Purple",          category="Fitness",     unit_cost=300, selling_price=999,  reorder_point=15, reorder_qty=75,  supplier_lead_days=7),
            Product(sku="DESK-LAMP-WHT",  name="LED Desk Lamp White",      category="Electronics", unit_cost=400, selling_price=1299, reorder_point=10, reorder_qty=40,  supplier_lead_days=10),
            Product(sku="NOTEBOOK-A5",    name="Hardcover Notebook A5",    category="Stationery",  unit_cost=60,  selling_price=249,  reorder_point=50, reorder_qty=300, supplier_lead_days=3),
        ]
        db.add_all(products)
        db.flush()

        # ── Inventory ─────────────────────────────────────────────────────────
        # Each product gets stock on both channels
        print("Seeding inventory...")
        stock_map = {
            "TSHIRT-RED-M":   {"shopify": 45, "amazon": 30},
            "TSHIRT-BLU-L":   {"shopify": 38, "amazon": 25},
            "EARBUDS-BLK":    {"shopify": 20, "amazon": 21},
            "EARBUDS-WHT":    {"shopify": 18, "amazon": 15},
            "WATERBOTTLE-1L": {"shopify": 60, "amazon": 55},
            "BACKPACK-BLK":   {"shopify": 12, "amazon": 8},
            "PHONE-CASE-S23": {"shopify": 85, "amazon": 70},
            "YOGA-MAT-PUR":   {"shopify": 22, "amazon": 18},
            "DESK-LAMP-WHT":  {"shopify": 14, "amazon": 11},
            "NOTEBOOK-A5":    {"shopify": 120, "amazon": 95},
        }

        channel_map = {"shopify": shopify, "amazon": amazon}

        for product in products:
            for channel_name, qty in stock_map[product.sku].items():
                inv = Inventory(
                    product_id=product.id,
                    channel_id=channel_map[channel_name].id,
                    quantity_on_hand=qty,
                    quantity_reserved=0,
                    version=0
                )
                db.add(inv)

        db.commit()
        print("Seed complete.")
        print(f"  Channels: 2 (shopify, amazon)")
        print(f"  Products: {len(products)}")
        print(f"  Inventory records: {len(products) * 2}")

    except Exception as e:
        db.rollback()
        print(f"Seed FAILED: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()