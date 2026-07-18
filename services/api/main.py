from fastapi import FastAPI
from contextlib import asynccontextmanager
import redis
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

# ---------------------------------------------------------------------------
# Lifespan — runs once on startup, once on shutdown
# This is the modern FastAPI way to handle startup/shutdown events
# ---------------------------------------------------------------------------
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
# Import routers — each file handles one group of endpoints
# ---------------------------------------------------------------------------
from services.api.routers import health, inventory, webhooks


app.include_router(health.router)
app.include_router(inventory.router, prefix="/inventory", tags=["Inventory"])
app.include_router(webhooks.router)