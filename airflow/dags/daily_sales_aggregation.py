from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta, timezone
import sys
import os

# ---------------------------------------------------------------------------
# Path setup — Airflow runs in its own container so we need to point at
# the database module mounted via the volume in docker-compose
# ---------------------------------------------------------------------------
sys.path.insert(0, "/opt/airflow")

default_args = {
    "owner": "inventory-platform",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}


def aggregate_daily_sales(**context):
    """
    Aggregates yesterday's sales from inventory_ledger into fact_daily_sales.
    Uses UPSERT (INSERT ... ON CONFLICT DO UPDATE) so re-running is safe.
    The execution_date from Airflow context tells us which day to aggregate.
    """
    from sqlalchemy import create_engine, text
    from datetime import date

    # execution_date is the logical date of the DAG run
    # For a daily DAG, this is yesterday when running at midnight
    execution_date = context["execution_date"]
    target_date = execution_date.date()

    print(f"Aggregating sales for: {target_date}")

    db_url = os.getenv(
        "POSTGRES_URL",
        "postgresql://postgres:mysecretpassword@postgres:5432/postgres"
    )
    engine = create_engine(db_url)

    with engine.begin() as conn:
        # Step 1 — aggregate from inventory_ledger for the target date
        result = conn.execute(text("""
            SELECT
                oi.product_id,
                o.channel_id,
                DATE(o.created_at) as sale_date,
                SUM(oi.quantity) as units_sold,
                SUM(oi.quantity * oi.unit_price) as revenue,
                AVG(oi.unit_price) as avg_price
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE DATE(o.created_at) = :target_date
              AND o.status = 'processed'
            GROUP BY oi.product_id, o.channel_id, DATE(o.created_at)
        """), {"target_date": target_date})

        rows = result.fetchall()
        print(f"  Found {len(rows)} product-channel combinations for {target_date}")

        if not rows:
            print(f"  No sales data for {target_date} — skipping")
            return

        # Step 2 — upsert into fact_daily_sales
        # ON CONFLICT means: if this date+product+channel already exists,
        # update it instead of inserting a duplicate
        for row in rows:
            conn.execute(text("""
                INSERT INTO analytics.fact_daily_sales
                    (id, sale_date, product_id, channel_id,
                     units_sold, revenue, avg_selling_price)
                VALUES
                    (gen_random_uuid(), :sale_date, :product_id, :channel_id,
                     :units_sold, :revenue, :avg_price)
                ON CONFLICT (sale_date, product_id, channel_id)
                DO UPDATE SET
                    units_sold = EXCLUDED.units_sold,
                    revenue = EXCLUDED.revenue,
                    avg_selling_price = EXCLUDED.avg_selling_price
            """), {
                "sale_date": row.sale_date,
                "product_id": str(row.product_id),
                "channel_id": str(row.channel_id),
                "units_sold": int(row.units_sold),
                "revenue": float(row.revenue) if row.revenue else 0.0,
                "avg_price": float(row.avg_price) if row.avg_price else 0.0,
            })

        print(f"  Upserted {len(rows)} rows into analytics.fact_daily_sales")


def check_low_stock(**context):
    """
    Second task in the DAG — runs after aggregation.
    Scans current inventory and logs any SKUs below reorder point.
    In production this would trigger WhatsApp alerts via Twilio.
    """
    from sqlalchemy import create_engine, text

    db_url = os.getenv(
        "POSTGRES_URL",
        "postgresql://postgres:mysecretpassword@postgres:5432/postgres"
    )
    engine = create_engine(db_url)

    with engine.begin() as conn:
        result = conn.execute(text("""
            SELECT
                p.sku,
                p.name,
                c.name as channel,
                i.quantity_on_hand,
                p.reorder_point,
                p.reorder_qty,
                p.supplier_lead_days
            FROM inventory i
            JOIN products p ON p.id = i.product_id
            JOIN channels c ON c.id = i.channel_id
            WHERE i.quantity_on_hand <= p.reorder_point
            ORDER BY i.quantity_on_hand ASC
        """))

        rows = result.fetchall()

        if not rows:
            print("All SKUs above reorder point — no action needed")
            return

        print(f"LOW STOCK REPORT — {len(rows)} SKUs need attention:")
        for row in rows:
            status = "STOCKOUT" if row.quantity_on_hand == 0 else "LOW"
            print(
                f"  [{status}] {row.sku} on {row.channel}: "
                f"{row.quantity_on_hand} units "
                f"(reorder: {row.reorder_point}, "
                f"order {row.reorder_qty} units, "
                f"lead: {row.supplier_lead_days} days)"
            )


with DAG(
    dag_id="daily_sales_aggregation",
    description="Aggregates daily sales into fact_daily_sales and checks low stock",
    default_args=default_args,
    start_date=datetime(2026, 1, 19),
    schedule_interval="0 0 * * *",  # midnight every day
    catchup=True,   # True = backfill all missed runs since start_date
    tags=["inventory", "analytics", "daily"],
) as dag:

    aggregate_task = PythonOperator(
        task_id="aggregate_daily_sales",
        python_callable=aggregate_daily_sales,
    )

    low_stock_task = PythonOperator(
        task_id="check_low_stock",
        python_callable=check_low_stock,
    )

    # Task dependency — low stock check runs after aggregation completes
    aggregate_task >> low_stock_task