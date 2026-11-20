"""Centralized, validated application configuration for SUJAAI.

Secrets are read only from the process environment or a local .env file.
Never commit a real .env file or expose Settings.secret_key in API responses.
"""
from __future__ import annotations

import os
import secrets
import warnings
from dataclasses import dataclass
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()


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
    max_request_body_bytes: int
    upload_dir: str

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def load_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if app_env not in {"development", "test", "staging", "production"}:
        raise RuntimeError("APP_ENV must be development, test, staging, or production")

    secret_key = os.getenv("SECRET_KEY", "").strip()
    if not secret_key and app_env in {"development", "test"}:
        secret_key = secrets.token_urlsafe(48)
        warnings.warn(
            "SECRET_KEY is not set; a temporary key was generated for this local process. "
            "Set SECRET_KEY in .env to keep sessions valid between restarts.",
            RuntimeWarning,
        )
    if len(secret_key) < 32:
        raise RuntimeError("SECRET_KEY is required and must contain at least 32 characters")

    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256").strip().upper()
    if jwt_algorithm != "HS256":
        raise RuntimeError("JWT_ALGORITHM currently supports HS256 only")

    try:
        token_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
        pool_size = int(os.getenv("DB_POOL_SIZE", "5"))
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "10"))
        pool_recycle = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800"))
        max_body = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(6 * 1024 * 1024)))
    except ValueError as exc:
        raise RuntimeError("Token, database pool, and request-size settings must be integers") from exc
    if not 5 <= token_minutes <= 1440:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 5 and 1440")
    if pool_size < 1 or max_overflow < 0 or pool_recycle < 60:
        raise RuntimeError("Database pool settings are outside their allowed range")
    if not 1024 <= max_body <= 25 * 1024 * 1024:
        raise RuntimeError("MAX_REQUEST_BODY_BYTES must be between 1 KB and 25 MB")

    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if app_env == "production":
        if not admin_email or "@" not in admin_email:
            raise RuntimeError("Set a valid ADMIN_EMAIL in the production backend environment")
        if len(admin_password) < 12:
            raise RuntimeError("Set ADMIN_PASSWORD with at least 12 characters in production")
    elif bool(admin_email) != bool(admin_password):
        raise RuntimeError("Set both ADMIN_EMAIL and ADMIN_PASSWORD, or leave both empty")

    database_url = os.getenv("DATABASE_URL", "sqlite:///./sujaai.db").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL cannot be empty")
    if app_env == "production" and database_url.startswith("sqlite"):
        raise RuntimeError("Production requires a persistent PostgreSQL DATABASE_URL; SQLite is not supported")

    frontend_url_raw = os.getenv("FRONTEND_URL", "").strip()
    frontend_url = _origin(frontend_url_raw, "FRONTEND_URL") if frontend_url_raw else ""
    raw_origins = _csv(os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"))
    origins = tuple(_origin(item, "CORS_ORIGINS") for item in raw_origins)
    if frontend_url and frontend_url not in origins:
        origins = (*origins, frontend_url)
    if app_env == "production" and not origins:
        raise RuntimeError("Set CORS_ORIGINS or FRONTEND_URL to your deployed frontend website origin")
    if "*" in origins:
        raise RuntimeError("Wildcard CORS origins are not allowed")

    return Settings(
        app_env=app_env,
        debug=os.getenv("DEBUG", "true" if app_env == "development" else "false").lower() in {"1", "true", "yes"},
        api_title=os.getenv("API_TITLE", "SUJAAI API").strip() or "SUJAAI API",
        api_version=os.getenv("API_VERSION", "0.3.0").strip() or "0.3.0",
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
        max_request_body_bytes=max_body,
        upload_dir=os.getenv("UPLOAD_DIR", "uploads").strip() or "uploads",
    )


settings = load_settings()
