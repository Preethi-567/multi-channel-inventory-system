from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import APIRouter
from fastapi.responses import Response

# ---------------------------------------------------------------------------
# Metrics definitions
# Every metric has a name, description, and optional label names.
# Labels let you slice the same metric by dimension —
# e.g. http_requests_total split by endpoint and method.
# ---------------------------------------------------------------------------

# HTTP request counter — incremented on every request
# Labels: method (GET/POST), endpoint (/inventory/summary), status_code (200/404/500)
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status_code"]
)

# HTTP request duration histogram
# Buckets define the boundaries for latency measurement
# e.g. "how many requests took between 0.1s and 0.25s?"
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# Cache metrics — lets us calculate hit rate: hits / (hits + misses)
CACHE_HITS = Counter(
    "redis_cache_hits_total",
    "Total Redis cache hits",
    ["endpoint"]
)

CACHE_MISSES = Counter(
    "redis_cache_misses_total",
    "Total Redis cache misses",
    ["endpoint"]
)

# Inventory update counter — how many inventory decrements have happened
INVENTORY_UPDATES = Counter(
    "inventory_updates_total",
    "Total inventory update operations",
    ["channel", "result"]  # result: success, insufficient_stock, dlq
)

# Kafka messages produced counter
KAFKA_MESSAGES_PRODUCED = Counter(
    "kafka_messages_produced_total",
    "Total Kafka messages produced",
    ["topic"]
)

# Kafka messages consumed counter
KAFKA_MESSAGES_CONSUMED = Counter(
    "kafka_messages_consumed_total",
    "Total Kafka messages consumed",
    ["topic", "result"]  # result: success, duplicate, dlq
)

# Active DB connections gauge — tracks connection pool usage
DB_CONNECTIONS_ACTIVE = Gauge(
    "db_connections_active",
    "Currently active database connections"
)

# Current inventory level gauge — updated on every sync
INVENTORY_LEVEL = Gauge(
    "inventory_level_units",
    "Current inventory level in units",
    ["sku", "channel"]
)

# Webhook events received
WEBHOOK_EVENTS = Counter(
    "webhook_events_total",
    "Total webhook events received",
    ["channel", "event_type"]
)

# ---------------------------------------------------------------------------
# /metrics endpoint — Prometheus scrapes this every 15 seconds
# ---------------------------------------------------------------------------
router = APIRouter(tags=["Metrics"])

@router.get("/metrics")
def metrics():
    """
    Prometheus scrapes this endpoint every 15 seconds.
    Returns all metrics in the Prometheus text exposition format.
    This is the standard format — Prometheus knows how to parse it.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )