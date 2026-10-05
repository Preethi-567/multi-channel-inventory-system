import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from fastapi import FastAPI
from contextlib import asynccontextmanager
import httpx
import asyncio
import random
from datetime import datetime, timezone
import uvicorn

WEBHOOK_TARGET = os.getenv("WEBHOOK_TARGET", "http://localhost:8000/webhooks/shopify")

PRODUCTS = [
    # Electronics
    {"sku": "EARBUDS-BLK",        "price": 2499.00},
    {"sku": "EARBUDS-WHT",        "price": 2499.00},
    {"sku": "DESK-LAMP-WHT",      "price": 1299.00},
    {"sku": "POWERBANK-10K",      "price": 1499.00},
    {"sku": "SPKR-BT-BLK",        "price": 1999.00},
    {"sku": "HEADPHONE-ANC-BLK",  "price": 3999.00},
    {"sku": "WEBCAM-1080P",        "price": 2299.00},
    {"sku": "MOUSE-WIRELESS-GRY", "price": 999.00},
    {"sku": "KEYBOARD-MECH-RGB",  "price": 4999.00},
    {"sku": "USB-HUB-7PORT",      "price": 899.00},
    # Fitness & Kitchen
    {"sku": "WATERBOTTLE-1L",     "price": 799.00},
    {"sku": "MUG-CERAMIC-BLK",    "price": 449.00},
    {"sku": "CUTTINGBOARD-WD",    "price": 649.00},
    {"sku": "CHEF-KNIFE-8IN",     "price": 1199.00},
    {"sku": "LUNCHBOX-STL",       "price": 799.00},
    {"sku": "YOGA-MAT-PUR",       "price": 999.00},
    {"sku": "DUMBBELL-5KG-PAIR",  "price": 1799.00},
    {"sku": "RES-BAND-SET",       "price": 599.00},
    {"sku": "SHAKER-BOTTLE-750",  "price": 499.00},
    {"sku": "FOAM-ROLLER-BLK",    "price": 849.00},
    # Accessories
    {"sku": "PHONE-CASE-S23",     "price": 349.00},
    {"sku": "CHARGER-CABLE-6FT",  "price": 399.00},
    {"sku": "WATCH-STRAP-BLK",    "price": 499.00},
    {"sku": "SUNGLASSES-POL-BLK", "price": 999.00},
    {"sku": "WALLET-LEATHER-BRN", "price": 1199.00},
    # Handmade Crafts
    {"sku": "MADHUBANI-PAINT",    "price": 3499.00},
    {"sku": "BRASS-GANESHA",      "price": 1599.00},
    {"sku": "JUTE-BASKET",        "price": 699.00},
    {"sku": "BLOCKPRINT-KURTA",   "price": 1299.00},
    {"sku": "COPPER-BOTTLE",      "price": 899.00},
    {"sku": "TERRACOTTA-POT",     "price": 549.00},
    {"sku": "SANDALWOOD-INCENSE", "price": 299.00},
    {"sku": "EMBROIDERED-CUSHION","price": 799.00},
    {"sku": "WARLI-FRAME",        "price": 1899.00},
    {"sku": "BAMBOO-TRAY",        "price": 1099.00},
]


def generate_shopify_order() -> dict:
    num_items = random.randint(1, 3)
    selected = random.sample(PRODUCTS, num_items)

    line_items = []
    for product in selected:
        line_items.append({
            "id": random.randint(100000, 999999),
            "sku": product["sku"],
            "quantity": random.randint(1, 3),
            "price": str(product["price"]),
            "title": product["sku"].replace("-", " ").title(),
        })

    order_id = random.randint(1000000, 9999999)

    return {
        "id": order_id,
        "order_number": f"#{random.randint(1000, 9999)}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "financial_status": "paid",
        "fulfillment_status": None,
        "currency": "INR",
        "total_price": str(sum(
            float(item["price"]) * item["quantity"]
            for item in line_items
        )),
        "line_items": line_items,
        "customer": {
            "id": random.randint(10000, 99999),
            "email": f"customer_{random.randint(1, 1000)}@example.com",
        },
        "shipping_address": {
            "city": random.choice(["Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad"]),
            "country": "India",
        }
    }


async def fire_webhook(client: httpx.AsyncClient, order: dict):
    try:
        response = await client.post(
            WEBHOOK_TARGET,
            json=order,
            timeout=10.0
        )
        sku_list = [item["sku"] for item in order["line_items"]]
        print(f"  Order {order['id']} → {sku_list} → {response.status_code}")
    except Exception as e:
        print(f"  Webhook failed: {e}")


async def order_simulator(interval_seconds: float = 5.0):
    print(f"Mock Shopify simulator started — firing orders every {interval_seconds}s")
    print(f"Target: {WEBHOOK_TARGET}\n")

    async with httpx.AsyncClient() as client:
        while True:
            order = generate_shopify_order()
            await fire_webhook(client, order)
            await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(order_simulator(interval_seconds=5.0))
    yield


app = FastAPI(title="Mock Shopify Server", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-shopify"}


@app.post("/trigger")
async def trigger_order():
    async with httpx.AsyncClient() as client:
        order = generate_shopify_order()
        await fire_webhook(client, order)
        return {"fired": order}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)