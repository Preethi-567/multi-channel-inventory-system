import psycopg2
import redis
from dotenv import load_dotenv
import os

# Load .env file so os.environ can see POSTGRES_URL and REDIS_URL
load_dotenv()

def test_postgres():
    print("Testing Postgres connection...")
    try:
        conn = psycopg2.connect(os.getenv("POSTGRES_URL"))
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        if version:
            print(f"  Postgres connected: {version[0]}") 
        cur.close()
        conn.close()
        print("  Connection closed cleanly.")
    except Exception as e:
        print(f"  Postgres FAILED: {e}")

def test_redis():
    print("Testing Redis connection...")
    try:
        r = redis.from_url(os.getenv("REDIS_URL"))
        r.ping()
        print("  Redis connected: PONG received")
    except Exception as e:
        print(f"  Redis FAILED: {e}")

if __name__ == "__main__":
    test_postgres()
    test_redis()