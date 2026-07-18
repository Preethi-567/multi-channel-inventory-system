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