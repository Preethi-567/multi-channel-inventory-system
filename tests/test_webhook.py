import requests
import json

# Test 1 — fire a Shopify order webhook
def test_shopify_webhook():
    payload = {
        "id": "12345",
        "line_items": [
            {"sku": "EARBUDS-BLK", "quantity": 2}
        ]
    }

    response = requests.post(
        "http://localhost:8000/webhooks/shopify",
        json=payload
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

# Test 2 — fire the same order again — tests idempotency key
def test_duplicate_webhook():
    payload = {
        "id": "12345",  # same order ID as above
        "line_items": [
            {"sku": "EARBUDS-BLK", "quantity": 2}
        ]
    }

    response = requests.post(
        "http://localhost:8000/webhooks/shopify",
        json=payload
    )

    print(f"\nDuplicate order status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")

if __name__ == "__main__":
    test_shopify_webhook()
    test_duplicate_webhook()