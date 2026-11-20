"""SUJAAI backend configuration.

QUICK SETUP
-----------
1. Change the non-secret defaults in CONFIG below if you want code-level defaults.
2. Put ADMIN_EMAIL, ADMIN_PASSWORD, SECRET_KEY and DATABASE_URL in backend/.env
   for local development, or in your hosting provider's Environment Variables.
3. Environment variables override CONFIG values.

Never put real passwords, signing keys, or database credentials in this file.
"""
from __future__ import annotations

import os
import secrets
import warnings
from dataclasses import dataclass
from urllib.parse import urlsplit

from dotenv import load_dotenv

# Loads backend/.env when running locally. Host environment variables take priority.
load_dotenv()

# ============================================================
# EASY CONFIGURATION: safe, non-secret defaults
# Edit these values to change local defaults for SUJAAI.
# For deployed environments, set the same names in Render/Vercel.
# ============================================================
CONFIG = {
    "APP_ENV": "development",                  # development | test | staging | production
    "DEBUG": False,                            # Keep False in production
    "API_TITLE": "SUJAAI API",
    "API_VERSION": "0.3.0",
    "JWT_ALGORITHM": "HS256",                  # Currently HS256 only
    "ACCESS_TOKEN_EXPIRE_MINUTES": 480,        # 8 hours
    "DATABASE_URL": "sqlite:///./sujaai.db",   # Production must use PostgreSQL
    "FRONTEND_URL": "http://localhost:5173",   # Main frontend website origin
    "CORS_ORIGINS": (
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    ),                                         # Add deployed frontend domains here
    "DB_POOL_SIZE": 5,
    "DB_MAX_OVERFLOW": 10,
    "DB_POOL_RECYCLE_SECONDS": 1800,
    "MAX_DESIGN_PAYLOAD_BYTES": 6 * 1024 * 1024,
    "UPLOAD_DIR": "uploads",
}

# Secret values are intentionally not stored in CONFIG.
SECRET_KEYS = ("SECRET_KEY", "ADMIN_EMAIL", "ADMIN_PASSWORD")


def _value(name: str, default=None):
    """Environment/.env value first; otherwise the editable CONFIG default."""
    return os.getenv(name, str(CONFIG.get(name, default)) if CONFIG.get(name, default) is not None else default)


def _csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(dict.fromkeys(part.strip().rstrip("/") for part in value.split(",") if part.strip()))


def _origin(value: str, variable: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError(f"{variable} must contain full website origins, e.g. https://example.com")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise RuntimeError(f"{variable} entries must be origins only (no path, query, or credentials): {value}")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise RuntimeError(f"{variable} must use HTTPS outside localhost")
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    debug: bool
    api_title: str
    api_version: str
    secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    admin_email: str
    admin_password: str
    database_url: str
    frontend_url: str
    cors_origins: tuple[str, ...]
    db_pool_size: int
    db_max_overflow: int
    db_pool_recycle_seconds: int
    max_design_payload_bytes: int
    upload_dir: str

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def load_settings() -> Settings:
    app_env = str(_value("APP_ENV", "development")).strip().lower()
    if app_env not in {"development", "test", "staging", "production"}:
        raise RuntimeError("APP_ENV must be development, test, staging, or production")

    secret_key = os.getenv("SECRET_KEY", "").strip()
    if not secret_key and app_env in {"development", "test"}:
        secret_key = secrets.token_urlsafe(48)
        warnings.warn(
            "SECRET_KEY is not set; a temporary key was generated for this local process. "
            "Set SECRET_KEY in backend/.env to keep sessions valid between restarts.",
            RuntimeWarning,
        )
    if len(secret_key) < 32:
        raise RuntimeError("SECRET_KEY is required and must contain at least 32 characters")

    jwt_algorithm = str(_value("JWT_ALGORITHM", "HS256")).strip().upper()
    if jwt_algorithm != "HS256":
        raise RuntimeError("JWT_ALGORITHM currently supports HS256 only")

    try:
        token_minutes = int(_value("ACCESS_TOKEN_EXPIRE_MINUTES", 480))
        pool_size = int(_value("DB_POOL_SIZE", 5))
        max_overflow = int(_value("DB_MAX_OVERFLOW", 10))
        pool_recycle = int(_value("DB_POOL_RECYCLE_SECONDS", 1800))
        max_payload = int(_value("MAX_DESIGN_PAYLOAD_BYTES", 6 * 1024 * 1024))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Token, database pool, and payload settings must be integers") from exc

    if not 5 <= token_minutes <= 1440:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 5 and 1440")
    if pool_size < 1 or max_overflow < 0 or pool_recycle < 60:
        raise RuntimeError("Database pool settings are outside their allowed range")
    if not 1024 <= max_payload <= 25 * 1024 * 1024:
        raise RuntimeError("MAX_DESIGN_PAYLOAD_BYTES must be between 1 KB and 25 MB")

    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if app_env == "production":
        if not admin_email or "@" not in admin_email:
            raise RuntimeError("Set a valid ADMIN_EMAIL in the backend environment")
        if len(admin_password) < 12:
            raise RuntimeError("Set ADMIN_PASSWORD with at least 12 characters")
    elif bool(admin_email) != bool(admin_password):
        raise RuntimeError("Set both ADMIN_EMAIL and ADMIN_PASSWORD, or leave both empty")

    database_url = str(_value("DATABASE_URL", "sqlite:///./sujaai.db")).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL cannot be empty")
    if app_env == "production" and database_url.startswith("sqlite"):
        raise RuntimeError("Production requires a persistent PostgreSQL DATABASE_URL; SQLite is not supported")

    frontend_raw = str(_value("FRONTEND_URL", "")).strip()
    frontend_url = _origin(frontend_raw, "FRONTEND_URL") if frontend_raw else ""
    origin_default = "" if app_env == "production" else "http://localhost:5173,http://127.0.0.1:5173"
    origins = tuple(
        _origin(item, "CORS_ORIGINS")
        for item in _csv(str(_value("CORS_ORIGINS", origin_default)))
    )
    if frontend_url and frontend_url not in origins:
        origins = (*origins, frontend_url)
    if app_env == "production" and not any(urlsplit(item).scheme == "https" for item in origins):
        raise RuntimeError("Set FRONTEND_URL or CORS_ORIGINS to at least one deployed HTTPS frontend origin")

    return Settings(
        app_env=app_env,
        debug=_bool(_value("DEBUG", app_env == "development")),
        api_title=str(_value("API_TITLE", "SUJAAI API")).strip() or "SUJAAI API",
        api_version=str(_value("API_VERSION", "0.3.0")).strip() or "0.3.0",
        secret_key=secret_key,
        jwt_algorithm=jwt_algorithm,
        access_token_expire_minutes=token_minutes,
        admin_email=admin_email,
        admin_password=admin_password,
        database_url=database_url,
        frontend_url=frontend_url,
        cors_origins=origins,
        db_pool_size=pool_size,
        db_max_overflow=max_overflow,
        db_pool_recycle_seconds=pool_recycle,
        max_design_payload_bytes=max_payload,
        upload_dir=str(_value("UPLOAD_DIR", "uploads")).strip() or "uploads",
    )


settings = load_settings()
