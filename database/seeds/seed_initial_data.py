import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from database.session import SessionLocal
from database.models import Product, Channel, Inventory
import uuid

def seed():
    db = SessionLocal()
    try:
        existing = db.query(Channel).first()
        if existing:
            print("Already seeded — skipping. Run reset_and_reseed.py first.")
            return

        # ── Channels ─────────────────────────────────────────────────────────
        print("Seeding channels...")
        shopify = Channel(id=uuid.uuid4(), name="shopify",
                         api_config={"webhook_url": "http://localhost:8001"}, is_active=True)
        amazon  = Channel(id=uuid.uuid4(), name="amazon",
                         api_config={"webhook_url": "http://localhost:8002"}, is_active=True)
        db.add_all([shopify, amazon])
        db.flush()

        # ── Products ──────────────────────────────────────────────────────────
        print("Seeding products...")
        products_data = [
            # Electronics
            dict(sku="EARBUDS-BLK",       name="Wireless Earbuds Black",       category="Electronics",      unit_cost=800,  selling_price=2499, reorder_point=20,  reorder_qty=60,  supplier_lead_days=14),
            dict(sku="EARBUDS-WHT",        name="Wireless Earbuds White",       category="Electronics",      unit_cost=800,  selling_price=2499, reorder_point=20,  reorder_qty=60,  supplier_lead_days=14),
            dict(sku="DESK-LAMP-WHT",      name="LED Desk Lamp White",          category="Electronics",      unit_cost=400,  selling_price=1299, reorder_point=15,  reorder_qty=50,  supplier_lead_days=10),
            dict(sku="POWERBANK-10K",      name="10000mAh Power Bank",          category="Electronics",      unit_cost=450,  selling_price=1499, reorder_point=25,  reorder_qty=80,  supplier_lead_days=10),
            dict(sku="SPKR-BT-BLK",       name="Bluetooth Speaker Black",      category="Electronics",      unit_cost=600,  selling_price=1999, reorder_point=15,  reorder_qty=50,  supplier_lead_days=12),
            dict(sku="HEADPHONE-ANC-BLK",  name="ANC Headphones Black",         category="Electronics",      unit_cost=1200, selling_price=3999, reorder_point=10,  reorder_qty=40,  supplier_lead_days=14),
            dict(sku="WEBCAM-1080P",       name="1080P Webcam",                 category="Electronics",      unit_cost=700,  selling_price=2299, reorder_point=10,  reorder_qty=35,  supplier_lead_days=12),
            dict(sku="MOUSE-WIRELESS-GRY", name="Wireless Mouse Grey",          category="Electronics",      unit_cost=350,  selling_price=999,  reorder_point=30,  reorder_qty=100, supplier_lead_days=7),
            dict(sku="KEYBOARD-MECH-RGB",  name="Mechanical Keyboard RGB",      category="Electronics",      unit_cost=1500, selling_price=4999, reorder_point=10,  reorder_qty=30,  supplier_lead_days=14),
            dict(sku="USB-HUB-7PORT",      name="7-Port USB Hub",               category="Electronics",      unit_cost=280,  selling_price=899,  reorder_point=25,  reorder_qty=80,  supplier_lead_days=7),

            # Fitness & Kitchen
            dict(sku="WATERBOTTLE-1L",     name="Steel Water Bottle 1L",        category="Fitness & Kitchen", unit_cost=200,  selling_price=799,  reorder_point=40,  reorder_qty=150, supplier_lead_days=5),
            dict(sku="MUG-CERAMIC-BLK",    name="Ceramic Mug Black 350ml",      category="Fitness & Kitchen", unit_cost=120,  selling_price=449,  reorder_point=50,  reorder_qty=200, supplier_lead_days=5),
            dict(sku="CUTTINGBOARD-WD",    name="Wooden Cutting Board",         category="Fitness & Kitchen", unit_cost=180,  selling_price=649,  reorder_point=30,  reorder_qty=100, supplier_lead_days=5),
            dict(sku="CHEF-KNIFE-8IN",     name="8-inch Chef Knife",            category="Fitness & Kitchen", unit_cost=350,  selling_price=1199, reorder_point=20,  reorder_qty=60,  supplier_lead_days=7),
            dict(sku="LUNCHBOX-STL",       name="Stainless Steel Lunchbox",     category="Fitness & Kitchen", unit_cost=220,  selling_price=799,  reorder_point=40,  reorder_qty=150, supplier_lead_days=5),
            dict(sku="YOGA-MAT-PUR",       name="Yoga Mat Purple",              category="Fitness & Kitchen", unit_cost=300,  selling_price=999,  reorder_point=25,  reorder_qty=80,  supplier_lead_days=7),
            dict(sku="DUMBBELL-5KG-PAIR",  name="5KG Dumbbell Pair",            category="Fitness & Kitchen", unit_cost=600,  selling_price=1799, reorder_point=15,  reorder_qty=40,  supplier_lead_days=10),
            dict(sku="RES-BAND-SET",       name="Resistance Band Set",          category="Fitness & Kitchen", unit_cost=180,  selling_price=599,  reorder_point=40,  reorder_qty=150, supplier_lead_days=5),
            dict(sku="SHAKER-BOTTLE-750",  name="Protein Shaker 750ml",         category="Fitness & Kitchen", unit_cost=150,  selling_price=499,  reorder_point=40,  reorder_qty=150, supplier_lead_days=5),
            dict(sku="FOAM-ROLLER-BLK",    name="Foam Roller Black",            category="Fitness & Kitchen", unit_cost=250,  selling_price=849,  reorder_point=20,  reorder_qty=80,  supplier_lead_days=7),

            # Accessories
            dict(sku="PHONE-CASE-S23",     name="Phone Case Samsung S23",       category="Accessories",       unit_cost=80,   selling_price=349,  reorder_point=50,  reorder_qty=200, supplier_lead_days=5),
            dict(sku="CHARGER-CABLE-6FT",  name="6ft Braided Charging Cable",   category="Accessories",       unit_cost=90,   selling_price=399,  reorder_point=60,  reorder_qty=250, supplier_lead_days=5),
            dict(sku="WATCH-STRAP-BLK",    name="Silicone Watch Strap Black",   category="Accessories",       unit_cost=120,  selling_price=499,  reorder_point=40,  reorder_qty=150, supplier_lead_days=5),
            dict(sku="SUNGLASSES-POL-BLK", name="Polarized Sunglasses Black",   category="Accessories",       unit_cost=300,  selling_price=999,  reorder_point=25,  reorder_qty=80,  supplier_lead_days=7),
            dict(sku="WALLET-LEATHER-BRN", name="Leather Wallet Brown",         category="Accessories",       unit_cost=350,  selling_price=1199, reorder_point=20,  reorder_qty=80,  supplier_lead_days=7),

            # Handmade Crafts
            dict(sku="MADHUBANI-PAINT",    name="Madhubani Painting A3",        category="Handmade Crafts",   unit_cost=1200, selling_price=3499, reorder_point=5,   reorder_qty=15,  supplier_lead_days=21),
            dict(sku="BRASS-GANESHA",      name="Brass Ganesha Idol 6 inch",    category="Handmade Crafts",   unit_cost=450,  selling_price=1599, reorder_point=8,   reorder_qty=25,  supplier_lead_days=14),
            dict(sku="JUTE-BASKET",        name="Handwoven Jute Basket",        category="Handmade Crafts",   unit_cost=180,  selling_price=699,  reorder_point=15,  reorder_qty=50,  supplier_lead_days=10),
            dict(sku="BLOCKPRINT-KURTA",   name="Block Print Cotton Kurta",     category="Handmade Crafts",   unit_cost=350,  selling_price=1299, reorder_point=10,  reorder_qty=35,  supplier_lead_days=14),
            dict(sku="COPPER-BOTTLE",      name="Pure Copper Water Bottle",     category="Handmade Crafts",   unit_cost=280,  selling_price=899,  reorder_point=20,  reorder_qty=60,  supplier_lead_days=7),
            dict(sku="TERRACOTTA-POT",     name="Terracotta Plant Pot Set",     category="Handmade Crafts",   unit_cost=150,  selling_price=549,  reorder_point=20,  reorder_qty=60,  supplier_lead_days=7),
            dict(sku="SANDALWOOD-INCENSE", name="Sandalwood Incense Sticks Box",category="Handmade Crafts",   unit_cost=90,   selling_price=299,  reorder_point=30,  reorder_qty=100, supplier_lead_days=5),
            dict(sku="EMBROIDERED-CUSHION",name="Hand Embroidered Cushion Cover",category="Handmade Crafts",  unit_cost=220,  selling_price=799,  reorder_point=15,  reorder_qty=50,  supplier_lead_days=10),
            dict(sku="WARLI-FRAME",        name="Warli Art Wall Frame",         category="Handmade Crafts",   unit_cost=500,  selling_price=1899, reorder_point=5,   reorder_qty=20,  supplier_lead_days=14),
            dict(sku="BAMBOO-TRAY",        name="Bamboo Serving Tray",          category="Handmade Crafts",   unit_cost=320,  selling_price=1099, reorder_point=15,  reorder_qty=50,  supplier_lead_days=7),
        ]

        products = [Product(**p) for p in products_data]
        db.add_all(products)
        db.flush()

        # ── Inventory ─────────────────────────────────────────────────────────
        print("Seeding inventory...")
        stock_map = {
            # Electronics — higher volume
            "EARBUDS-BLK":        {"shopify": 120, "amazon": 100},
            "EARBUDS-WHT":        {"shopify": 110, "amazon": 90},
            "DESK-LAMP-WHT":      {"shopify": 80,  "amazon": 65},
            "POWERBANK-10K":      {"shopify": 150, "amazon": 120},
            "SPKR-BT-BLK":        {"shopify": 90,  "amazon": 75},
            "HEADPHONE-ANC-BLK":  {"shopify": 60,  "amazon": 50},
            "WEBCAM-1080P":        {"shopify": 70,  "amazon": 55},
            "MOUSE-WIRELESS-GRY": {"shopify": 180, "amazon": 150},
            "KEYBOARD-MECH-RGB":  {"shopify": 55,  "amazon": 45},
            "USB-HUB-7PORT":      {"shopify": 160, "amazon": 130},
            # Fitness & Kitchen
            "WATERBOTTLE-1L":     {"shopify": 200, "amazon": 180},
            "MUG-CERAMIC-BLK":    {"shopify": 250, "amazon": 200},
            "CUTTINGBOARD-WD":    {"shopify": 150, "amazon": 120},
            "CHEF-KNIFE-8IN":     {"shopify": 90,  "amazon": 75},
            "LUNCHBOX-STL":       {"shopify": 180, "amazon": 150},
            "YOGA-MAT-PUR":       {"shopify": 120, "amazon": 100},
            "DUMBBELL-5KG-PAIR":  {"shopify": 70,  "amazon": 55},
            "RES-BAND-SET":       {"shopify": 200, "amazon": 170},
            "SHAKER-BOTTLE-750":  {"shopify": 190, "amazon": 160},
            "FOAM-ROLLER-BLK":    {"shopify": 110, "amazon": 90},
            # Accessories — highest volume
            "PHONE-CASE-S23":     {"shopify": 300, "amazon": 250},
            "CHARGER-CABLE-6FT":  {"shopify": 350, "amazon": 300},
            "WATCH-STRAP-BLK":    {"shopify": 200, "amazon": 170},
            "SUNGLASSES-POL-BLK": {"shopify": 150, "amazon": 120},
            "WALLET-LEATHER-BRN": {"shopify": 120, "amazon": 100},
            # Handmade Crafts — lower volume, handmade
            "MADHUBANI-PAINT":    {"shopify": 30,  "amazon": 20},
            "BRASS-GANESHA":      {"shopify": 45,  "amazon": 35},
            "JUTE-BASKET":        {"shopify": 60,  "amazon": 50},
            "BLOCKPRINT-KURTA":   {"shopify": 40,  "amazon": 30},
            "COPPER-BOTTLE":      {"shopify": 70,  "amazon": 55},
            "TERRACOTTA-POT":     {"shopify": 65,  "amazon": 50},
            "SANDALWOOD-INCENSE": {"shopify": 120, "amazon": 100},
            "EMBROIDERED-CUSHION":{"shopify": 50,  "amazon": 40},
            "WARLI-FRAME":        {"shopify": 25,  "amazon": 18},
            "BAMBOO-TRAY":        {"shopify": 70,  "amazon": 55},
        }

        channel_map = {"shopify": shopify, "amazon": amazon}
        for product in products:
            for channel_name, qty in stock_map[product.sku].items():
                db.add(Inventory(
                    product_id=product.id,
                    channel_id=channel_map[channel_name].id,
                    quantity_on_hand=qty,
                    quantity_reserved=0,
                    version=0
                ))

        db.commit()
        print(f"Seed complete — {len(products)} products, {len(products)*2} inventory records")

    except Exception as e:
        db.rollback()
        print(f"Seed FAILED: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()