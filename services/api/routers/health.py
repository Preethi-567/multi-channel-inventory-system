from fastapi import APIRouter
from database.session import SessionLocal
import redis as redis_lib
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """
    Checks all three dependencies — Postgres, Redis.
    Returns their status so you know exactly what's alive.
    Load balancer hits this endpoint to know if the service is healthy.
    """
    status = {
        "status": "ok",
        "postgres": "unknown",
        "redis": "unknown",
    }

    # Check Postgres use connection pool instead of creating a new connection each time
    try:
        db = SessionLocal()
        db.execute(__import__('sqlalchemy').text("SELECT 1"))
        db.close()
        status["postgres"] = "connected"
    except Exception as e:
        status["postgres"] = f"error: {str(e)}"
        status["status"] = "degraded"

    # Check Redis
    try:
        r = redis_lib.from_url(os.getenv("REDIS_URL",""))
        r.ping()
        status["redis"] = "connected"
    except Exception as e:
        status["redis"] = f"error: {str(e)}"
        status["status"] = "degraded"

    return status