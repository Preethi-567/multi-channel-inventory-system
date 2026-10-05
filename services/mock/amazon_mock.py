import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from fastapi import FastAPI
from contextlib import asynccontextmanager
import httpx
import asyncio
import random
import uuid
from datetime import datetime, timezone
import uvicorn

WEBHOOK_TARGET = os.getenv("AMAZON_WEBHOOK_TARGET", "http://localhost:8000/webhooks/amazon")

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

# Amazon marketplace IDs for India
MARKETPLACE_IDS = ["A21TJRUUN4KGV"]  # Amazon.in

# Amazon order statuses
ORDER_STATUSES = ["Unshipped", "PartiallyShipped"]


def generate_amazon_order() -> dict:
    """
    Generates a realistic Amazon SP-API order payload.
    Format matches real Amazon order notification format.
    """
    num_items = random.randint(1, 3)
    selected = random.sample(PRODUCTS, num_items)

    order_items = []
    for product in selected:
        qty = random.randint(1, 3)
        order_items.append({
            "ASIN": f"B{random.randint(10000000, 99999999)}",
            "SellerSKU": product["sku"],
            "OrderItemId": str(random.randint(10000000000000, 99999999999999)),
            "Title": product["sku"].replace("-", " ").title(),
            "QuantityOrdered": qty,
            "QuantityShipped": 0,
            "ItemPrice": {
                "CurrencyCode": "INR",
                "Amount": str(product["price"] * qty)
            },
            "ItemTax": {
                "CurrencyCode": "INR",
                "Amount": str(round(product["price"] * qty * 0.18, 2))
            }
        })

    amazon_order_id = f"402-{random.randint(1000000, 9999999)}-{random.randint(1000000, 9999999)}"

    return {
        "AmazonOrderId": amazon_order_id,
        "PurchaseDate": datetime.now(timezone.utc).isoformat(),
        "LastUpdateDate": datetime.now(timezone.utc).isoformat(),
        "OrderStatus": random.choice(ORDER_STATUSES),
        "FulfillmentChannel": "MFN",  # Merchant Fulfilled Network
        "SalesChannel": "Amazon.in",
        "MarketplaceId": random.choice(MARKETPLACE_IDS),
        "OrderTotal": {
            "CurrencyCode": "INR",
            "Amount": str(sum(
                float(item["ItemPrice"]["Amount"])
                for item in order_items
            ))
        },
        "NumberOfItemsShipped": 0,
        "NumberOfItemsUnshipped": len(order_items),
        "PaymentMethod": "COD",
        "ShippingAddress": {
            "Name": f"Customer {random.randint(1000, 9999)}",
            "AddressLine1": f"{random.randint(1, 999)} Main Street",
            "City": random.choice([
                "Mumbai", "Delhi", "Bangalore",
                "Chennai", "Hyderabad", "Pune", "Kolkata"
            ]),
            "StateOrRegion": random.choice([
                "Maharashtra", "Delhi", "Karnataka",
                "Tamil Nadu", "Telangana"
            ]),
            "PostalCode": str(random.randint(100000, 999999)),
            "CountryCode": "IN"
        },
        "OrderItems": order_items
    }


async def fire_webhook(client: httpx.AsyncClient, order: dict):
    try:
        response = await client.post(
            WEBHOOK_TARGET,
            json=order,
            timeout=10.0
        )
        sku_list = [item["SellerSKU"] for item in order["OrderItems"]]
        print(f"  Amazon Order {order['AmazonOrderId']} → {sku_list} → {response.status_code}")
    except Exception as e:
        print(f"  Amazon webhook failed: {e}")


async def order_simulator(interval_seconds: float = 7.0):
    """
    Fires a new Amazon order every 7 seconds.
    Slightly slower than Shopify (5s) to simulate realistic ratio.
    """
    print(f"Mock Amazon simulator started — firing orders every {interval_seconds}s")
    print(f"Target: {WEBHOOK_TARGET}\n")

    async with httpx.AsyncClient() as client:
        while True:
            order = generate_amazon_order()
            await fire_webhook(client, order)
            await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(order_simulator(interval_seconds=7.0))
    yield


app = FastAPI(
    title="Mock Amazon SP-API Server",
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "mock-amazon"}


@app.post("/trigger")
async def trigger_order():
    async with httpx.AsyncClient() as client:
        order = generate_amazon_order()
        await fire_webhook(client, order)
        return {"fired": order}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)