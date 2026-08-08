import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def reset_database():
    engine = create_engine(
        os.getenv("POSTGRES_URL", "postgresql://postgres:mysecretpassword@localhost:5432/postgres")
    )
    
    print("Wiping all existing data...")
    with engine.begin() as conn:
        # Order matters — foreign keys
        conn.execute(text("DELETE FROM analytics.forecast_results"))
        conn.execute(text("DELETE FROM analytics.fact_daily_sales"))
        conn.execute(text("DELETE FROM public.alerts"))
        conn.execute(text("DELETE FROM public.inventory_ledger"))
        conn.execute(text("DELETE FROM public.order_items"))
        conn.execute(text("DELETE FROM public.orders"))
        conn.execute(text("DELETE FROM public.inventory"))
        conn.execute(text("DELETE FROM public.products"))
        conn.execute(text("DELETE FROM public.channels"))
    print("All data wiped.")

if __name__ == "__main__":
    reset_database()
    print("Ready for reseed.")