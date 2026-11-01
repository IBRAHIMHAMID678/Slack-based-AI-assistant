"""Database engine initialization, connection pooling, and WAL mode configuration.

Ensures SQLite runs with WAL (Write-Ahead Logging), 30-second busy timeout,
and enforced foreign keys for concurrent persistence resilience.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.models import Base
from app.logging import get_logger

logger = get_logger("db_migrate")

# Configure SQLite engine with appropriate timeout and isolation
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30.0},
    echo=False,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # type: ignore
    """Enable SQLite WAL journal mode and foreign key enforcement."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all schema tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)
    logger.info("database_schema_initialized", url=settings.DATABASE_URL)


def get_db_session() -> OrmSession:
    """Provide a database session for synchronous or repository contexts."""
    return SessionLocal()
