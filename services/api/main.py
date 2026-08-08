from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import time
import os
from dotenv import load_dotenv

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Inventory Platform API...")
    yield
    print("Shutting down Inventory Platform API...")

app = FastAPI(
    title="Inventory Platform API",
    description="Multi-channel inventory management and demand forecasting",
    version="0.1.0",
    lifespan=lifespan
)

# ---------------------------------------------------------------------------
# Prometheus middleware — runs on EVERY request automatically
# This is how we track latency and request count without touching each endpoint
# ---------------------------------------------------------------------------
@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    """
    Intercepts every HTTP request.
    Records the endpoint, method, duration, and status code.
    This runs before and after every endpoint function.
    """
    from services.api.metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_DURATION

    # Normalize path — replace UUIDs and SKUs with placeholders
    # Without this, /inventory/EARBUDS-BLK and /inventory/NOTEBOOK-A5
    # would be tracked as separate endpoints, exploding cardinality
    path = request.url.path
    if path.startswith("/inventory/") and path not in [
        "/inventory/summary", "/inventory/alerts",
        "/inventory/forecasts", "/metrics"
    ]:
        path = "/inventory/{sku}"

    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    method = request.method
    status = str(response.status_code)

    # Record metrics
    HTTP_REQUESTS_TOTAL.labels(
        method=method,
        endpoint=path,
        status_code=status
    ).inc()

    HTTP_REQUEST_DURATION.labels(
        method=method,
        endpoint=path
    ).observe(duration)

    return response


# ---------------------------------------------------------------------------
# Import and register routers
# ---------------------------------------------------------------------------
from services.api.routers import health, inventory, webhooks, analytics
from services.api.metrics import router as metrics_router

app.include_router(metrics_router)
app.include_router(health.router)
app.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
app.include_router(webhooks.router)
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])