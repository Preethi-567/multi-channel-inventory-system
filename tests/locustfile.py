from locust import HttpUser, task, between
import random

# ---------------------------------------------------------------------------
# Locust simulates real user behavior — not just hammering one endpoint.
# Each "user" follows a realistic pattern:
#   - Check inventory summary (most common action)
#   - Look up a specific SKU
#   - Check alerts
#   - Place an order via webhook (less frequent)
#
# between(1, 3) means each user waits 1-3 seconds between actions
# This simulates realistic think time — users don't hammer instantly
# ---------------------------------------------------------------------------

SKUS = [
    "TSHIRT-RED-M", "TSHIRT-BLU-L", "EARBUDS-BLK", "EARBUDS-WHT",
    "WATERBOTTLE-1L", "BACKPACK-BLK", "PHONE-CASE-S23",
    "YOGA-MAT-PUR", "DESK-LAMP-WHT", "NOTEBOOK-A5"
]

SHOPIFY_ORDER_TEMPLATE = {
    "financial_status": "paid",
    "currency": "INR",
    "line_items": []
}


class InventoryUser(HttpUser):
    """
    Simulates a user of the inventory platform.
    Weight=3 means 3x more read users than write users — realistic ratio.
    """
    weight = 3
    wait_time = between(1, 3)

    @task(5)
    def view_inventory_summary(self):
        """
        Most common action — checking overall inventory.
        task(5) means this runs 5x more often than task(1) actions.
        """
        with self.client.get(
            "/inventory/summary",
            name="/inventory/summary",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "data" not in data:
                    response.failure("Missing 'data' key in response")
            else:
                response.failure(f"Status {response.status_code}")

    @task(3)
    def view_single_sku(self):
        """
        Look up a random SKU — simulates searching for a product.
        """
        sku = random.choice(SKUS)
        with self.client.get(
            f"/inventory/{sku}",
            name="/inventory/{sku}",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.failure(f"SKU {sku} not found")
            else:
                response.failure(f"Status {response.status_code}")

    @task(2)
    def view_alerts(self):
        """Check active alerts — dashboard polling behavior."""
        self.client.get("/inventory/alerts", name="/inventory/alerts")

    @task(1)
    def view_forecasts(self):
        """Check forecast data — less frequent than inventory checks."""
        self.client.get("/inventory/forecasts", name="/inventory/forecasts")

    @task(1)
    def health_check(self):
        """Health check — simulates load balancer probing."""
        self.client.get("/health", name="/health")


class OrderUser(HttpUser):
    """
    Simulates order webhooks arriving — write traffic.
    Weight=1 means fewer order users than read users.
    """
    weight = 1
    wait_time = between(2, 5)

    @task
    def place_shopify_order(self):
        """
        Fires a realistic Shopify order webhook.
        Uses random SKUs and quantities to simulate real order variety.
        """
        num_items = random.randint(1, 3)
        selected_skus = random.sample(SKUS, num_items)

        line_items = [
            {
                "id": random.randint(100000, 999999),
                "sku": sku,
                "quantity": random.randint(1, 2),
                "price": str(random.choice([249, 349, 599, 799, 999, 1299, 1999, 2499])),
            }
            for sku in selected_skus
        ]

        payload = {
            "id": random.randint(1000000, 9999999),
            "financial_status": "paid",
            "currency": "INR",
            "line_items": line_items,
        }

        with self.client.post(
            "/webhooks/shopify",
            json=payload,
            name="/webhooks/shopify",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Webhook failed: {response.status_code}")