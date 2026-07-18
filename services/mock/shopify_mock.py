import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from fastapi import FastAPI
import httpx
import asyncio
import random
import uuid
from datetime import datetime, timezone
import uvicorn
import os
from contextlib import asynccontextmanager

WEBHOOK_TARGET = os.getenv("WEBHOOK_TARGET", "http://localhost:8000/webhooks/shopify")

PRODUCTS = [
    {"sku": "TSHIRT-RED-M",   "price": 599.00},
    {"sku": "TSHIRT-BLU-L",   "price": 599.00},
    {"sku": "EARBUDS-BLK",    "price": 2499.00},
    {"sku": "EARBUDS-WHT",    "price": 2499.00},
    {"sku": "WATERBOTTLE-1L", "price": 799.00},
    {"sku": "BACKPACK-BLK",   "price": 1999.00},
    {"sku": "PHONE-CASE-S23", "price": 349.00},
    {"sku": "YOGA-MAT-PUR",   "price": 999.00},
    {"sku": "DESK-LAMP-WHT",  "price": 1299.00},
    {"sku": "NOTEBOOK-A5",    "price": 249.00},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(order_simulator(interval_seconds=5.0))
    yield

app = FastAPI(title="Mock Shopify Server", version="0.1.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# The FastAPI endpoint your real server posts to
# ---------------------------------------------------------------------------
WEBHOOK_TARGET = os.getenv("WEBHOOK_TARGET", "http://localhost:8000/webhooks/shopify")

# ---------------------------------------------------------------------------
# Product catalog — must match SKUs in your database
# ---------------------------------------------------------------------------
PRODUCTS = [
    {"sku": "TSHIRT-RED-M",   "price": 599.00},
    {"sku": "TSHIRT-BLU-L",   "price": 599.00},
    {"sku": "EARBUDS-BLK",    "price": 2499.00},
    {"sku": "EARBUDS-WHT",    "price": 2499.00},
    {"sku": "WATERBOTTLE-1L", "price": 799.00},
    {"sku": "BACKPACK-BLK",   "price": 1999.00},
    {"sku": "PHONE-CASE-S23", "price": 349.00},
    {"sku": "YOGA-MAT-PUR",   "price": 999.00},
    {"sku": "DESK-LAMP-WHT",  "price": 1299.00},
    {"sku": "NOTEBOOK-A5",    "price": 249.00},
]


def generate_shopify_order() -> dict:
    """
    Generates a realistic Shopify order payload.
    Format matches real Shopify webhook payloads exactly.
    """
    # Pick 1-3 random products for this order
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
    """
    Fires a single order webhook to your FastAPI endpoint.
    Prints the result so you can watch orders flowing in real time.
    """
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
    """
    Fires a new random order every `interval_seconds`.
    Runs forever until Ctrl+C.
    """
    print(f"Mock Shopify simulator started — firing orders every {interval_seconds}s")
    print(f"Target: {WEBHOOK_TARGET}\n")

    async with httpx.AsyncClient() as client:
        while True:
            order = generate_shopify_order()
            await fire_webhook(client, order)
            await asyncio.sleep(interval_seconds)


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(order_simulator(interval_seconds=5.0))
    yield


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-shopify"}


@app.post("/trigger")
async def trigger_order():
    """
    Manually trigger a single order — useful for testing.
    Hit POST /trigger to fire one order immediately.
    """
    async with httpx.AsyncClient() as client:
        order = generate_shopify_order()
        await fire_webhook(client, order)
        return {"fired": order}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)