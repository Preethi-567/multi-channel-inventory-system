from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import redis as redis_lib
import json
import os
from dotenv import load_dotenv

from database.session import get_db
from database.models import Product, Inventory, Channel

load_dotenv()

router = APIRouter()

# Redis client — one instance reused across requests
redis_client = redis_lib.from_url(os.getenv("REDIS_URL",""), decode_responses=True)

# Cache TTL — 30 seconds
CACHE_TTL = 30


@router.get("/summary")
def get_inventory_summary(db: Session = Depends(get_db)):
    """
    Returns all SKUs with current stock levels across all channels.

    Cache strategy — cache-aside pattern:
    1. Check Redis for cached result
    2. Cache hit → return immediately (fast path, no DB query)
    3. Cache miss → query Postgres, write result to Redis, return result

    Why 30 seconds TTL: inventory changes on every order. Caching longer
    risks showing stale stock. 30 seconds is a reasonable balance between
    freshness and reducing DB load.
    """
    cache_key = "inventory:summary"

    # Step 1 — check Redis first
    cached = redis_client.get(cache_key)
    if cached:
        # Cache hit — deserialize and return immediately
        return {"source": "cache", "data": json.loads(cached)}

    # Step 2 — cache miss — query Postgres
    # Join inventory → products → channels to get everything in one query
    rows = (
        db.query(
            Product.sku,
            Product.name,
            Product.reorder_point,
            Channel.name.label("channel"),
            Inventory.quantity_on_hand,
            Inventory.quantity_reserved,
        )
        .join(Inventory, Inventory.product_id == Product.id)
        .join(Channel, Channel.id == Inventory.channel_id)
        .order_by(Product.sku, Channel.name)
        .all()
    )

    # Step 3 — reshape into nested structure: one entry per SKU,
    # with a list of channel stock levels inside
    summary = {}
    for row in rows:
        if row.sku not in summary:
            summary[row.sku] = {
                "sku": row.sku,
                "name": row.name,
                "reorder_point": row.reorder_point,
                "total_stock": 0,
                "channels": [],
                "low_stock": False,
            }

        qty_available = row.quantity_on_hand - row.quantity_reserved
        summary[row.sku]["channels"].append({
            "channel": row.channel,
            "quantity_on_hand": row.quantity_on_hand,
            "quantity_reserved": row.quantity_reserved,
            "quantity_available": qty_available,
        })
        summary[row.sku]["total_stock"] += row.quantity_on_hand

    # Step 4 — compute low_stock flag per SKU
    result = list(summary.values())
    for item in result:
        item["low_stock"] = item["total_stock"] < item["reorder_point"]

    # Step 5 — write to Redis with 30 second TTL
    redis_client.setex(cache_key, CACHE_TTL, json.dumps(result))

    return {"source": "database", "data": result}


@router.get("/{sku}")
def get_inventory_by_sku(sku: str, db: Session = Depends(get_db)):
    """
    Returns stock levels for a single SKU across all channels.
    Same cache-aside pattern as summary, but keyed per SKU.
    """
    cache_key = f"inventory:{sku}"

    # Check cache first
    cached = redis_client.get(cache_key)
    if cached:
        return {"source": "cache", "data": json.loads(cached)}

    # Query Postgres
    rows = (
        db.query(
            Product.sku,
            Product.name,
            Product.reorder_point,
            Product.supplier_lead_days,
            Channel.name.label("channel"),
            Inventory.quantity_on_hand,
            Inventory.quantity_reserved,
        )
        .join(Inventory, Inventory.product_id == Product.id)
        .join(Channel, Channel.id == Inventory.channel_id)
        .filter(Product.sku == sku.upper())
        .order_by(Channel.name)
        .all()
    )

    if not rows:
        raise HTTPException(status_code=404, detail=f"SKU '{sku}' not found")

    # Build response
    result = {
        "sku": rows[0].sku,
        "name": rows[0].name,
        "reorder_point": rows[0].reorder_point,
        "supplier_lead_days": rows[0].supplier_lead_days,
        "total_stock": 0,
        "channels": [],
        "low_stock": False,
    }

    for row in rows:
        qty_available = row.quantity_on_hand - row.quantity_reserved
        result["channels"].append({
            "channel": row.channel,
            "quantity_on_hand": row.quantity_on_hand,
            "quantity_reserved": row.quantity_reserved,
            "quantity_available": qty_available,
        })
        result["total_stock"] += row.quantity_on_hand

    result["low_stock"] = result["total_stock"] < result["reorder_point"]

    # Cache it
    redis_client.setex(cache_key, CACHE_TTL, json.dumps(result))

    return {"source": "database", "data": result}

from database.models import Alert

@router.get("/alerts")
def get_alerts(unread_only: bool = True, db: Session = Depends(get_db)):
    """
    Returns all alerts, optionally filtered to unread only.
    """
    query = db.query(
        Alert,
        Product.sku,
        Product.name,
        Channel.name.label("channel_name")
    ).join(Product, Product.id == Alert.product_id)\
     .join(Channel, Channel.id == Alert.channel_id)

    if unread_only:
        query = query.filter(Alert.is_read == False)

    query = query.order_by(Alert.created_at.desc())
    rows = query.all()

    return {
        "total": len(rows),
        "alerts": [
            {
                "id": str(row.Alert.id),
                "sku": row.sku,
                "product_name": row.name,
                "channel": row.channel_name,
                "alert_type": row.Alert.alert_type,
                "severity": row.Alert.severity,
                "message": row.Alert.message,
                "is_read": row.Alert.is_read,
                "created_at": row.Alert.created_at.isoformat(),
            }
            for row in rows
        ]
    }