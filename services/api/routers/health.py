from fastapi import APIRouter
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

    # Check Postgres
    try:
        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        conn.close()
        status["postgres"] = "connected"
    except Exception as e:
        status["postgres"] = f"error: {str(e)}"
        status["status"] = "degraded"

    # Check Redis
    try:
        r = redis_lib.from_url(os.getenv("REDIS_URL"))
        r.ping()
        status["redis"] = "connected"
    except Exception as e:
        status["redis"] = f"error: {str(e)}"
        status["status"] = "degraded"

    return status