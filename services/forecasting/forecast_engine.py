import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from sqlalchemy import create_engine, text
from prophet import Prophet
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import warnings
import uuid
warnings.filterwarnings("ignore")  # Prophet is chatty

load_dotenv()

HORIZON_DAYS = 30  # forecast 30 days ahead
MIN_HISTORY_DAYS = 30  # need at least 30 days of data to forecast


def get_db_engine():
    return create_engine(
        os.getenv("POSTGRES_URL", "postgresql://postgres:mysecretpassword@localhost:5432/postgres")
    )


def load_sales_history(engine, product_id: str, channel_id: str) -> pd.DataFrame:
    """
    Loads daily sales history for a product+channel from fact_daily_sales.
    Returns a DataFrame with columns [ds, y] — Prophet's required format.
    ds = date, y = units sold
    """
    query = text("""
        SELECT sale_date as ds, units_sold as y
        FROM analytics.fact_daily_sales
        WHERE product_id = :product_id
          AND channel_id = :channel_id
        ORDER BY sale_date
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {
            "product_id": product_id,
            "channel_id": channel_id
        })
        rows = result.fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["ds", "y"])
    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = df["y"].astype(float)
    return df


def run_prophet_forecast(df: pd.DataFrame, horizon: int = HORIZON_DAYS) -> pd.DataFrame:
    """
    Fits a Prophet model on historical sales and forecasts `horizon` days ahead.

    Prophet requires:
    - Column 'ds' (datetime): the date
    - Column 'y' (float): the metric to forecast

    Why Prophet:
    - Handles weekly seasonality automatically (weekends vs weekdays)
    - Handles yearly seasonality (Diwali spike)
    - Robust to missing data and outliers
    - No hyperparameter tuning needed for MVP
    - Returns confidence intervals (yhat_lower, yhat_upper)
    """
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        seasonality_mode="multiplicative",  # better for retail — spikes multiply baseline
        interval_width=0.80,  # 80% confidence interval
    )

    model.fit(df)

    # Create future dataframe — Prophet needs this to know what dates to forecast
    future = model.make_future_dataframe(periods=horizon, freq="D")
    forecast = model.predict(future)

    # Only return the forecast period, not the historical fit
    forecast_only = forecast[forecast["ds"] > df["ds"].max()].copy()
    forecast_only["yhat"] = forecast_only["yhat"].clip(lower=0)  # no negative sales
    forecast_only["yhat_lower"] = forecast_only["yhat_lower"].clip(lower=0)
    forecast_only["yhat_upper"] = forecast_only["yhat_upper"].clip(lower=0)

    return forecast_only[["ds", "yhat", "yhat_lower", "yhat_upper"]]


def calculate_stockout_date(
    current_stock: int,
    forecast_df: pd.DataFrame,
    supplier_lead_days: int
) -> tuple:
    """
    Walks through the forecast day by day, subtracting predicted sales
    from current stock until it hits zero.

    Returns (stockout_date, reorder_flag):
    - stockout_date: predicted date stock runs out (None if stock lasts beyond horizon)
    - reorder_flag: True if stockout is within supplier_lead_days
    """
    remaining = current_stock
    stockout_date = None

    for _, row in forecast_df.iterrows():
        daily_demand = max(0, round(row["yhat"]))
        remaining -= daily_demand

        if remaining <= 0:
            stockout_date = row["ds"].date()
            break

    reorder_flag = False
    if stockout_date:
        days_until_stockout = (stockout_date - date.today()).days
        reorder_flag = days_until_stockout <= supplier_lead_days

    return stockout_date, reorder_flag


def save_forecast_results(engine, product_id: str, forecast_df: pd.DataFrame,
                           stockout_date, reorder_flag: bool, mape: float = None):
    """
    Saves forecast results to analytics.forecast_results.
    Uses UPSERT to make re-runs idempotent.
    """
    with engine.begin() as conn:
        for _, row in forecast_df.iterrows():
            conn.execute(text("""
                INSERT INTO analytics.forecast_results
                    (id, product_id, forecast_date, generated_at, horizon_days,
                     predicted_units, lower_bound, upper_bound,
                     model_mape, stockout_date, reorder_flag)
                VALUES
                    (gen_random_uuid(), :product_id, :forecast_date, NOW(),
                     :horizon_days, :predicted_units, :lower_bound, :upper_bound,
                     :model_mape, :stockout_date, :reorder_flag)
                ON CONFLICT DO NOTHING
            """), {
                "product_id": product_id,
                "forecast_date": row["ds"].date(),
                "horizon_days": HORIZON_DAYS,
                "predicted_units": round(float(row["yhat"]), 2),
                "lower_bound": round(float(row["yhat_lower"]), 2),
                "upper_bound": round(float(row["yhat_upper"]), 2),
                "model_mape": round(mape, 2) if mape else None,
                "stockout_date": stockout_date,
                "reorder_flag": reorder_flag,
            })


def calculate_mape(df: pd.DataFrame, model: Prophet) -> float:
    """
    Calculates Mean Absolute Percentage Error on historical data.
    Lower is better. Under 20% is good for retail forecasting.
    """
    try:
        historical_forecast = model.predict(df[["ds"]])
        actual = df["y"].values
        predicted = historical_forecast["yhat"].values
        mask = actual > 0
        if mask.sum() == 0:
            return None
        mape = np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100
        return float(mape)
    except Exception:
        return None


def run_forecasts_for_all_skus():
    """
    Main entry point — runs Prophet for every product+channel combination.
    Called by Airflow DAG or directly for testing.
    """
    engine = get_db_engine()

    # Load all product+channel combinations that have sales history
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT DISTINCT
                f.product_id,
                f.channel_id,
                p.sku,
                p.name,
                c.name as channel_name,
                p.supplier_lead_days,
                i.quantity_on_hand as current_stock
            FROM analytics.fact_daily_sales f
            JOIN products p ON p.id = f.product_id
            JOIN channels c ON c.id = f.channel_id
            JOIN inventory i ON i.product_id = f.product_id
                             AND i.channel_id = f.channel_id
            ORDER BY p.sku, c.name
        """))
        combinations = result.fetchall()

    print(f"Running forecasts for {len(combinations)} product-channel combinations...")
    print(f"Horizon: {HORIZON_DAYS} days\n")

    results_summary = []

    for row in combinations:
        product_id = str(row.product_id)
        channel_id = str(row.channel_id)
        sku = row.sku
        channel_name = row.channel_name
        supplier_lead_days = row.supplier_lead_days
        current_stock = row.current_stock

        print(f"Forecasting: {sku} on {channel_name} (stock: {current_stock})")

        # Load history
        df = load_sales_history(engine, product_id, channel_id)

        if len(df) < MIN_HISTORY_DAYS:
            print(f"  Skipping — only {len(df)} days of history (need {MIN_HISTORY_DAYS})")
            continue

        try:
            # Fit model and forecast
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                seasonality_mode="multiplicative",
                interval_width=0.80,
            )
            model.fit(df)
            forecast_df = run_prophet_forecast(df, HORIZON_DAYS)

            # Calculate MAPE
            mape = calculate_mape(df, model)

            # Calculate stockout date
            stockout_date, reorder_flag = calculate_stockout_date(
                current_stock, forecast_df, supplier_lead_days
            )

            # Save results
            save_forecast_results(
                engine, product_id, forecast_df,
                stockout_date, reorder_flag, mape
            )

            # Summary line
            stockout_str = str(stockout_date) if stockout_date else f">{HORIZON_DAYS}d"
            mape_str = f"{mape:.1f}%" if mape else "N/A"
            reorder_str = "⚠️ REORDER NOW" if reorder_flag else "ok"
            print(f"  Stockout: {stockout_str} | MAPE: {mape_str} | {reorder_str}")

            results_summary.append({
                "sku": sku,
                "channel": channel_name,
                "stock": current_stock,
                "stockout": stockout_str,
                "reorder": reorder_flag
            })

        except Exception as e:
            print(f"  FAILED: {e}")
            continue

    print(f"\nForecast complete — {len(results_summary)} SKUs processed")

    # Print reorder alerts
    reorder_needed = [r for r in results_summary if r["reorder"]]
    if reorder_needed:
        print(f"\n⚠️  REORDER ALERTS ({len(reorder_needed)} SKUs):")
        for r in reorder_needed:
            print(f"  {r['sku']} on {r['channel']}: stock={r['stock']}, stockout={r['stockout']}")
    else:
        print("\nNo immediate reorder alerts.")


if __name__ == "__main__":
    run_forecasts_for_all_skus()