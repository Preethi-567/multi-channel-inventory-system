from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

# The engine is the connection pool — one engine for the whole application.
# pool_pre_ping=True means SQLAlchemy checks if a connection is still alive
# before using it. Prevents "connection closed" errors after idle periods.
engine = create_engine(
    os.getenv("POSTGRES_URL",""),
    pool_pre_ping=True,
    pool_size=10,  # maintain 20 persistent connections 
    max_overflow=10,  # allow up to 10 additional connections (for bursts)
    pool_timeout=30,  # wait up to 30 seconds for a connection before raising an error
    pool_recycle=1800,  # recycle connections every 30 minutes to avoid stale connections
    echo=False  # Set to True temporarily if you want to see every SQL query
)

# SessionLocal is a factory — every time you call SessionLocal() you get
# a new session (think: a unit of work with its own transaction).
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """
    Dependency function for FastAPI endpoints.
    Yields a session, then closes it automatically when the request is done.
    Usage in FastAPI: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()