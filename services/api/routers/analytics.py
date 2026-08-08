from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from datetime import datetime, timedelta

from database.session import get_db
from database.models import Product

router = APIRouter()


@router.get("/profitability")
def get_profitability(db: Session = Depends(get_db)):
    """
    Returns per-SKU profitability analysis ranked by restock priority.

    Priority score = margin_percent × units_sold_last_30d
    High margin + high sales = restock first.
    Low margin + low sales = restock last.
    """

    cutoff = datetime.utcnow() - timedelta(days=30)

    # Pull sales data from analytics schema for last 30 days
    sales_query = text("""
        SELECT
            p.id,
            p.sku,
            p.name,
            p.category,
            p.unit_cost,
            p.selling_price,
            p.reorder_qty,
            COALESCE(SUM(f.units_sold), 0)  AS units_sold_30d,
            COALESCE(SUM(f.revenue), 0)     AS revenue_30d
        FROM public.products p
        LEFT JOIN analytics.fact_daily_sales f
            ON f.product_id = p.id
            AND f.sale_date >= :cutoff
        GROUP BY p.id, p.sku, p.name, p.unit_cost, p.selling_price, p.reorder_qty
        ORDER BY p.sku
    """)

    rows = db.execute(sales_query, {"cutoff": cutoff.date()}).fetchall()

    result = []
    for row in rows:
        unit_cost      = float(row.unit_cost or 0)
        selling_price  = float(row.selling_price or 0)
        units_sold     = int(row.units_sold_30d or 0)
        revenue        = float(row.revenue_30d or 0)
        reorder_qty    = int(row.reorder_qty or 0)

        profit_per_unit = selling_price - unit_cost
        margin_percent  = round((profit_per_unit / selling_price * 100), 1) if selling_price > 0 else 0
        total_profit    = round(profit_per_unit * units_sold, 2)
        restock_cost    = round(unit_cost * reorder_qty, 2)
        priority_score  = round(margin_percent * units_sold, 2)

        result.append({
            "sku":              row.sku,
            "name":             row.name,
            "category":         row.category or "Uncategorized",
            "selling_price":    selling_price,
            "unit_cost":        unit_cost,
            "profit_per_unit":  round(profit_per_unit, 2),
            "margin_percent":   margin_percent,
            "units_sold_30d":   units_sold,
            "revenue_30d":      round(revenue, 2),
            "total_profit_30d": total_profit,
            "reorder_qty":      reorder_qty,
            "restock_cost":     restock_cost,
            "priority_score":   priority_score,
        })

    # Sort by priority score — highest first
    result.sort(key=lambda x: x["priority_score"], reverse=True)

    return {
        "period_days": 30,
        "total_skus": len(result),
        "products": result
    }


@router.get("/sales-velocity")
def get_sales_velocity(days: int = 7, db: Session = Depends(get_db)):
    """
    Top and bottom movers by units sold in the last N days.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = text("""
        SELECT
            p.sku,
            p.name,
            COALESCE(SUM(f.units_sold), 0) AS units_sold,
            COALESCE(SUM(f.revenue), 0)    AS revenue
        FROM public.products p
        LEFT JOIN analytics.fact_daily_sales f
            ON f.product_id = p.id
            AND f.sale_date >= :cutoff
        GROUP BY p.sku, p.name
        ORDER BY units_sold DESC
    """)

    rows = db.execute(query, {"cutoff": cutoff.date()}).fetchall()

    products = [
        {
            "sku":        row.sku,
            "name":       row.name,
            "units_sold": int(row.units_sold),
            "revenue":    float(row.revenue),
        }
        for row in rows
    ]

    return {
        "period_days": days,
        "top_movers":    products[:5],
        "bottom_movers": list(reversed(products[-5:])),
    }