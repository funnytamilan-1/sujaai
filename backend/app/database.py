"""SQLAlchemy database engine and request-scoped sessions."""
from sqlalchemy import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


def normalize_database_url(url: str) -> str:
    """Normalize hosted PostgreSQL URLs to the psycopg 3 SQLAlchemy driver."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


DATABASE_URL = normalize_database_url(settings.database_url)
is_sqlite = DATABASE_URL.startswith("sqlite")

connect_args = {}
if is_sqlite:
    # Avoid SQLite's short default lock wait when concurrent requests write.
    connect_args = {"check_same_thread": False, "timeout": 30}

engine_options = {
    "pool_pre_ping": settings.db_pool_pre_ping,
    "pool_recycle": settings.db_pool_recycle_seconds,
}
if not is_sqlite:
    # Vercel creates multiple short-lived function instances. Keep each
    # instance's pool small so aggregate connections do not overwhelm Postgres.
    on_vercel = os.getenv("VERCEL", "").lower() == "1"
    engine_options.update(
        pool_size=1 if on_vercel else settings.db_pool_size,
        max_overflow=0 if on_vercel else settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
    )

engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_options)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def _configure_sqlite_connection(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    """Yield one SQLAlchemy session per request and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
