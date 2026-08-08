# Inventory Brain
**Intelligent Multi-Channel Inventory Management & Demand Forecasting Platform**

Built for Indian SMBs selling across Shopify and Amazon simultaneously.
Real-time inventory sync, Prophet-based demand forecasting, and profitability analytics — all in one platform.

---

## What This System Does

> "When a sale happens on Shopify, the system knows in under 5 seconds, updates Amazon's inventory, predicts when you'll run out of stock, and tells you exactly how much to reorder — automatically."

- **Real-time sync** across Shopify and Amazon via Kafka event pipeline
- **Race-condition-safe** inventory updates using optimistic locking
- **Idempotency** — duplicate webhooks never double-decrement stock
- **30-day demand forecasts** per SKU using Facebook Prophet
- **Profitability analytics** with ABC classification across 4 product categories
- **Live observability** via Prometheus + Grafana (8-panel dashboard)

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI (Python 3.10) |
| Event Bus | Apache Kafka (Confluent 7.4) |
| Database | PostgreSQL 15 (dual-schema: OLTP + Analytics) |
| Cache | Redis 7 |
| Orchestration | Apache Airflow 2.9 |
| Forecasting | Facebook Prophet |
| Dashboard | React 18 + Recharts + Vite |
| Observability | Prometheus + Grafana |
| Infrastructure | Docker Compose |

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker Desktop | 29.x+ | Must be running before `docker-compose up` |
| Python | 3.10.x | Specifically 3.10 — Prophet + Airflow compatibility |
| Node.js | 18.x+ | For React dashboard |
| Git | Any | |

Install Python dependencies:
```bash
pip install -r requirements.txt
```

Install dashboard dependencies:
```bash
cd services/dashboard
npm install
```

---

## One-Command Startup

```bash
git clone <your-repo-url>
cd inventory-platform
docker-compose up -d
```

Wait 30 seconds for all services to initialize, then run:

```bash
# Activate virtual environment
venv\Scripts\Activate.ps1          # Windows PowerShell
# source venv/bin/activate         # Mac/Linux

# Seed the database (35 products across 4 categories)
python database/seeds/seed_initial_data.py

# Generate 6 months of synthetic sales history
python database/seeds/generate_synthetic_sales.py

# Populate analytics fact table
docker exec -it my-airflow airflow dags trigger daily_sales_aggregation

# Run demand forecasts
python services/forecasting/forecast_engine.py
```

---

## Starting All Services

Open 7 terminals from the project root:

| Terminal | Command |
|---|---|
| 1 — Docker | `docker-compose start` |
| 2 — FastAPI | `uvicorn services.api.main:app --reload --port 8000` |
| 3 — Dashboard | `cd services/dashboard && npm run dev` |
| 4 — Mock Shopify | `python services/mock/shopify_mock.py` |
| 5 — Mock Amazon | `python services/mock/amazon_mock.py` |
| 6 — Sync Consumer | `python services/consumers/sync_consumer.py` |
| 7 — Alert Consumer | `python services/consumers/alert_consumer.py` |

---

## Service URLs

| Service | URL | Notes |
|---|---|---|
| React Dashboard | http://localhost:3000 | Main UI |
| FastAPI | http://localhost:8000 | REST API |
| API Docs (Swagger) | http://localhost:8000/docs | Auto-generated |
| Grafana | http://localhost:3001 | admin / admin |
| Prometheus | http://localhost:9090 | Metrics scraping |
| Airflow | http://localhost:8080 | admin / admin |

---

## Product Catalogue (35 SKUs across 4 categories)

| Category | SKUs | Example |
|---|---|---|
| Electronics | 10 | EARBUDS-BLK, KEYBOARD-MECH-RGB, WEBCAM-1080P |
| Fitness & Kitchen | 10 | YOGA-MAT-PUR, CHEF-KNIFE-8IN, WATERBOTTLE-1L |
| Accessories | 5 | CHARGER-CABLE-6FT, WALLET-LEATHER-BRN |
| Handmade Crafts | 10 | MADHUBANI-PAINT, BRASS-GANESHA, WARLI-FRAME |

---

## Project Structure

inventory-platform/
├── services/
│ ├── api/ # FastAPI — ingestion + read layer
│ │ ├── main.py # App entry point, middleware
│ │ └── routers/ # inventory.py, analytics.py, webhooks.py
│ ├── consumers/
│ │ ├── sync_consumer.py # Kafka → Postgres inventory updates
│ │ └── alert_consumer.py # Stock threshold monitoring
│ ├── dashboard/ # React + Vite frontend
│ ├── forecasting/
│ │ └── forecast_engine.py # Prophet per-SKU demand forecasting
│ └── mock/
│ ├── shopify_mock.py # Simulates Shopify webhooks (every 5s)
│ └── amazon_mock.py # Simulates Amazon SP-API (every 7s)
├── database/
│ ├── models.py # SQLAlchemy ORM models
│ ├── seeds/
│ │ ├── seed_initial_data.py
│ │ ├── generate_synthetic_sales.py
│ │ └── reset_and_reseed.py
│ └── session.py
├── airflow/dags/
│ └── daily_sales_aggregation.py
├── monitoring/
│ ├── prometheus.yml
│ └── grafana-dashboard.json
├── alembic/ # Database migrations
├── docker-compose.yml
└── requirements.txt


---

## Key Architecture Decisions

### Why Kafka instead of direct DB writes?
Kafka absorbs order bursts during flash sales. During load testing at 200 concurrent users, the pipeline maintained 81.9 RPS with 0% read failures. If the consumer crashes, events replay from the last committed offset — no data loss.

### Why optimistic locking?
`SELECT FOR UPDATE` holds row locks during the entire transaction. Under high concurrency this creates a queue and degrades throughput. Optimistic locking (version column + conditional UPDATE) only retries on actual conflicts, which are rare in normal operation.

### Why two Postgres schemas?
Heavy analytics queries (GROUP BY, window functions over 180 days) must never lock OLTP inventory tables. A flash sale and a weekly report running simultaneously must not block each other.

---

## Performance Benchmarks (Locust load test — 200 concurrent users)

| Metric | Result |
|---|---|
| Median latency (aggregated) | 110ms |
| p95 latency | < 200ms |
| Throughput | 81.9 RPS |
| Read failure rate | 0% |
| Redis cache hit rate | 95%+ |
| Inventory sync latency p95 | < 5 seconds |

---

## Database Schema

**Public schema (OLTP):** `products`, `channels`, `inventory`, `orders`, `order_items`, `inventory_ledger`, `alerts`

**Analytics schema:** `fact_daily_sales`, `forecast_results`

Reset and reseed:
```bash
python database/seeds/reset_and_reseed.py
python database/seeds/seed_initial_data.py
python database/seeds/generate_synthetic_sales.py
```

---

## Running Tests

```bash
# End-to-end sync test
python -m pytest tests/test_sync_consumer.py -v

# Idempotency test — same order twice, stock decrements once
python -m pytest tests/test_idempotency.py -v

# Race condition test — 10 concurrent orders, zero negative inventory
python -m pytest tests/test_race_condition.py -v
```
---

## Built With

This project was built as part of the **Kalpana – She for STEM Accelerator** program.
Every component was built hands-on and understood before implementation — no black boxes.