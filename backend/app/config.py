"""Central configuration for the SUJAAI backend.

QUICK EDIT (local development)
------------------------------
Edit the individual uppercase variables in the EASY EDIT SETTINGS section.
For example: APP_NAME is API_TITLE, and the website URL is FRONTEND_URL.

IMPORTANT:
- Never put real passwords, SECRET_KEY, API tokens or production DB passwords here.
- Put secrets in backend/.env locally, or your hosting provider's Environment Variables.
- Environment variables override the code defaults below.
- FRONTEND_URL and CORS_ORIGINS are website origins only (no /login, /api or paths).

Example deployed frontend:
    FRONTEND_URL = "https://your-site.vercel.app"
    CORS_ORIGINS = "https://your-site.vercel.app"
Example backend URL (set in frontend/.env, not here):
    VITE_API_BASE_URL = "https://your-api.vercel.app"
"""
from __future__ import annotations

import os
import secrets
import warnings
from dataclasses import dataclass
from urllib.parse import urlsplit

from dotenv import load_dotenv

# Loads backend/.env for local development. Real process environment wins.
load_dotenv()

# =====================================================================
# EASY EDIT SETTINGS — change individual variables in this section.
# Environment variables override these defaults.
# Never put real passwords, SECRET_KEY, API tokens or DB passwords here.
# =====================================================================

# APP
APP_ENV = "development"              # development | test | staging | production
DEBUG = False
API_TITLE = "SUJAAI API"
API_VERSION = "0.3.0"
APP_TIMEZONE = "Asia/Kolkata"

# SECURITY (non-secret settings only)
JWT_ALGORITHM = "HS256"              # This application currently supports HS256 only
ACCESS_TOKEN_EXPIRE_MINUTES = 480    # 8 hours; allowed range: 5–1440
PASSWORD_MIN_LENGTH = 12

# DATABASE
DATABASE_URL = "sqlite:///./sujaai.db"  # Production: set PostgreSQL URL in hosting env
DB_POOL_SIZE = 5
DB_MAX_OVERFLOW = 10
DB_POOL_RECYCLE_SECONDS = 1800
DB_POOL_TIMEOUT_SECONDS = 30
DB_POOL_PRE_PING = True

# FRONTEND / CORS
FRONTEND_URL = "https://sujaa.vercel.app"
CORS_ORIGINS = "https://sujaa.vercel.app"
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
CORS_ALLOW_HEADERS = "Authorization,Content-Type"

# REQUEST / DATA LIMITS
MAX_DESIGN_PAYLOAD_BYTES = 3 * 1024 * 1024
MAX_REQUEST_BODY_BYTES = 4 * 1024 * 1024
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500

# FILE / STORAGE
UPLOAD_DIR = "uploads"
ALLOWED_UPLOAD_EXTENSIONS = ".jpg,.jpeg,.png,.webp,.pdf,.xlsx,.csv"

# Keep these compatibility dictionaries for any existing imports/code.
APP_CONFIG = {
    "environment": APP_ENV, "debug": DEBUG, "name": API_TITLE,
    "version": API_VERSION, "timezone": APP_TIMEZONE,
}
SECURITY_CONFIG = {
    "jwt_algorithm": JWT_ALGORITHM,
    "access_token_expire_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
    "password_min_length": PASSWORD_MIN_LENGTH,
}
DATABASE_CONFIG = {
    "url": DATABASE_URL, "pool_size": DB_POOL_SIZE,
    "max_overflow": DB_MAX_OVERFLOW,
    "pool_recycle_seconds": DB_POOL_RECYCLE_SECONDS,
    "pool_timeout_seconds": DB_POOL_TIMEOUT_SECONDS,
    "pool_pre_ping": DB_POOL_PRE_PING,
}
CORS_CONFIG = {
    "frontend_url": FRONTEND_URL, "origins": CORS_ORIGINS,
    "allow_credentials": CORS_ALLOW_CREDENTIALS,
    "allow_methods": CORS_ALLOW_METHODS, "allow_headers": CORS_ALLOW_HEADERS,
}
LIMITS_CONFIG = {
    "max_design_payload_bytes": MAX_DESIGN_PAYLOAD_BYTES,
    "max_request_body_bytes": MAX_REQUEST_BODY_BYTES,
    "default_page_size": DEFAULT_PAGE_SIZE, "max_page_size": MAX_PAGE_SIZE,
}
STORAGE_CONFIG = {
    "upload_dir": UPLOAD_DIR, "allowed_upload_extensions": ALLOWED_UPLOAD_EXTENSIONS,
}

# Flatten settings so existing application imports remain compatible.
# Edit the individual variables above; do not edit this generated mapping.
CONFIG = {
    "APP_ENV": APP_CONFIG["environment"],
    "DEBUG": APP_CONFIG["debug"],
    "API_TITLE": APP_CONFIG["name"],
    "API_VERSION": APP_CONFIG["version"],
    "APP_TIMEZONE": APP_CONFIG["timezone"],
    "JWT_ALGORITHM": SECURITY_CONFIG["jwt_algorithm"],
    "ACCESS_TOKEN_EXPIRE_MINUTES": SECURITY_CONFIG["access_token_expire_minutes"],
    "PASSWORD_MIN_LENGTH": SECURITY_CONFIG["password_min_length"],
    "DATABASE_URL": DATABASE_CONFIG["url"],
    "DB_POOL_SIZE": DATABASE_CONFIG["pool_size"],
    "DB_MAX_OVERFLOW": DATABASE_CONFIG["max_overflow"],
    "DB_POOL_RECYCLE_SECONDS": DATABASE_CONFIG["pool_recycle_seconds"],
    "DB_POOL_TIMEOUT_SECONDS": DATABASE_CONFIG["pool_timeout_seconds"],
    "DB_POOL_PRE_PING": DATABASE_CONFIG["pool_pre_ping"],
    "FRONTEND_URL": CORS_CONFIG["frontend_url"],
    "CORS_ORIGINS": CORS_CONFIG["origins"],
    "CORS_ALLOW_CREDENTIALS": CORS_CONFIG["allow_credentials"],
    "CORS_ALLOW_METHODS": CORS_CONFIG["allow_methods"],
    "CORS_ALLOW_HEADERS": CORS_CONFIG["allow_headers"],
    "MAX_DESIGN_PAYLOAD_BYTES": LIMITS_CONFIG["max_design_payload_bytes"],
    "MAX_REQUEST_BODY_BYTES": LIMITS_CONFIG["max_request_body_bytes"],
    "DEFAULT_PAGE_SIZE": LIMITS_CONFIG["default_page_size"],
    "MAX_PAGE_SIZE": LIMITS_CONFIG["max_page_size"],
    "UPLOAD_DIR": STORAGE_CONFIG["upload_dir"],
    "ALLOWED_UPLOAD_EXTENSIONS": STORAGE_CONFIG["allowed_upload_extensions"],
}

# Secrets must come from environment variables, never the committed source file.
SECRET_KEYS = ("SECRET_KEY", "ADMIN_EMAIL", "ADMIN_PASSWORD")


def _value(name: str, default=None):
    fallback = CONFIG.get(name, default)
    if fallback is None:
        return os.getenv(name)
    return os.getenv(name, str(fallback))


def _bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


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


@dataclass(frozen=True, kw_only=True)
class Settings:
    app_env: str
    debug: bool
    api_title: str
    api_version: str
    app_timezone: str
    secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    password_min_length: int
    admin_email: str
    admin_password: str
    database_url: str
    db_pool_size: int
    db_max_overflow: int
    db_pool_recycle_seconds: int
    db_pool_timeout_seconds: int
    db_pool_pre_ping: bool
    frontend_url: str
    cors_origins: tuple[str, ...]
    cors_allow_credentials: bool
    cors_allow_methods: tuple[str, ...]
    cors_allow_headers: tuple[str, ...]
    max_design_payload_bytes: int
    max_request_body_bytes: int
    default_page_size: int
    max_page_size: int
    upload_dir: str
    allowed_upload_extensions: tuple[str, ...]

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
            "SECRET_KEY is not set; a temporary key was generated for this process. "
            "Set SECRET_KEY in backend/.env to keep sessions valid after restart.",
            RuntimeWarning,
        )
    if len(secret_key) < 32:
        raise RuntimeError("SECRET_KEY is required and must contain at least 32 characters")

    jwt_algorithm = str(_value("JWT_ALGORITHM", "HS256")).strip().upper()
    if jwt_algorithm != "HS256":
        raise RuntimeError("JWT_ALGORITHM currently supports HS256 only")

    try:
        integer_settings = {
            "token_minutes": int(_value("ACCESS_TOKEN_EXPIRE_MINUTES", 480)),
            "password_min": int(_value("PASSWORD_MIN_LENGTH", 12)),
            "pool_size": int(_value("DB_POOL_SIZE", 5)),
            "max_overflow": int(_value("DB_MAX_OVERFLOW", 10)),
            "pool_recycle": int(_value("DB_POOL_RECYCLE_SECONDS", 1800)),
            "pool_timeout": int(_value("DB_POOL_TIMEOUT_SECONDS", 30)),
            "max_design": int(_value("MAX_DESIGN_PAYLOAD_BYTES", 6 * 1024 * 1024)),
            "max_body": int(_value("MAX_REQUEST_BODY_BYTES", 10 * 1024 * 1024)),
            "page_size": int(_value("DEFAULT_PAGE_SIZE", 100)),
            "max_page_size": int(_value("MAX_PAGE_SIZE", 500)),
        }
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Numeric configuration values must be valid integers") from exc

    if not 5 <= integer_settings["token_minutes"] <= 1440:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be between 5 and 1440")
    if not 8 <= integer_settings["password_min"] <= 128:
        raise RuntimeError("PASSWORD_MIN_LENGTH must be between 8 and 128")
    if integer_settings["pool_size"] < 1 or integer_settings["max_overflow"] < 0:
        raise RuntimeError("DB_POOL_SIZE must be >= 1 and DB_MAX_OVERFLOW must be >= 0")
    if integer_settings["pool_recycle"] < 60 or integer_settings["pool_timeout"] < 1:
        raise RuntimeError("Database pool recycle/timeout values are too small")
    if not 1024 <= integer_settings["max_design"] <= 25 * 1024 * 1024:
        raise RuntimeError("MAX_DESIGN_PAYLOAD_BYTES must be between 1 KB and 25 MB")
    if not 1024 <= integer_settings["max_body"] <= 50 * 1024 * 1024:
        raise RuntimeError("MAX_REQUEST_BODY_BYTES must be between 1 KB and 50 MB")
    if not 1 <= integer_settings["page_size"] <= integer_settings["max_page_size"] <= 2000:
        raise RuntimeError("Page-size settings must satisfy 1 <= DEFAULT_PAGE_SIZE <= MAX_PAGE_SIZE <= 2000")

    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if app_env == "production":
        if not admin_email or "@" not in admin_email:
            raise RuntimeError("Set a valid ADMIN_EMAIL in the backend environment")
        if len(admin_password) < integer_settings["password_min"]:
            raise RuntimeError(f"Set ADMIN_PASSWORD with at least {integer_settings['password_min']} characters")
    elif bool(admin_email) != bool(admin_password):
        raise RuntimeError("Set both ADMIN_EMAIL and ADMIN_PASSWORD, or leave both empty")

    database_url = str(_value("DATABASE_URL", "sqlite:///./sujaai.db")).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL cannot be empty")
    if app_env == "production" and database_url.startswith("sqlite"):
        raise RuntimeError("Production requires a persistent PostgreSQL DATABASE_URL; SQLite is not supported")
    if app_env == "production" and not database_url.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
        raise RuntimeError("Production DATABASE_URL must be a PostgreSQL connection URL")

    frontend_raw = str(_value("FRONTEND_URL", "")).strip()
    frontend_url = _origin(frontend_raw, "FRONTEND_URL") if frontend_raw else ""
    origin_default = "" if app_env == "production" else "http://localhost:5173,http://127.0.0.1:5173"
    origins = tuple(_origin(item, "CORS_ORIGINS") for item in _csv(str(_value("CORS_ORIGINS", origin_default))))
    if frontend_url and frontend_url not in origins:
        origins = (*origins, frontend_url)
    if app_env == "production" and not any(urlsplit(item).scheme == "https" for item in origins):
        raise RuntimeError("Set FRONTEND_URL or CORS_ORIGINS to at least one deployed HTTPS frontend origin")

    methods = tuple(item.strip().upper() for item in _csv(str(_value("CORS_ALLOW_METHODS", "GET,POST,PUT,PATCH,DELETE,OPTIONS"))))
    headers = tuple(item.strip() for item in _csv(str(_value("CORS_ALLOW_HEADERS", "Authorization,Content-Type"))))
    if not methods or not headers:
        raise RuntimeError("CORS_ALLOW_METHODS and CORS_ALLOW_HEADERS cannot be empty")

    extensions = tuple(item.strip().lower() for item in _csv(str(_value("ALLOWED_UPLOAD_EXTENSIONS", ".jpg,.jpeg,.png,.webp,.pdf,.xlsx,.csv"))))
    if any(not item.startswith(".") for item in extensions):
        raise RuntimeError("ALLOWED_UPLOAD_EXTENSIONS entries must start with a dot")

    return Settings(
        app_env=app_env,
        debug=_bool(_value("DEBUG", app_env == "development")),
        api_title=str(_value("API_TITLE", "SUJAAI API")).strip() or "SUJAAI API",
        api_version=str(_value("API_VERSION", "0.3.0")).strip() or "0.3.0",
        app_timezone=str(_value("APP_TIMEZONE", "Asia/Kolkata")).strip() or "Asia/Kolkata",
        secret_key=secret_key,
        jwt_algorithm=jwt_algorithm,
        access_token_expire_minutes=integer_settings["token_minutes"],
        password_min_length=integer_settings["password_min"],
        admin_email=admin_email,
        admin_password=admin_password,
        database_url=database_url,
        db_pool_size=integer_settings["pool_size"],
        db_max_overflow=integer_settings["max_overflow"],
        db_pool_recycle_seconds=integer_settings["pool_recycle"],
        db_pool_timeout_seconds=integer_settings["pool_timeout"],
        db_pool_pre_ping=_bool(_value("DB_POOL_PRE_PING", True)),
        frontend_url=frontend_url,
        cors_origins=origins,
        cors_allow_credentials=_bool(_value("CORS_ALLOW_CREDENTIALS", True)),
        cors_allow_methods=methods,
        cors_allow_headers=headers,
        max_design_payload_bytes=integer_settings["max_design"],
        max_request_body_bytes=integer_settings["max_body"],
        default_page_size=integer_settings["page_size"],
        max_page_size=integer_settings["max_page_size"],
        upload_dir=str(_value("UPLOAD_DIR", "uploads")).strip() or "uploads",
        allowed_upload_extensions=extensions,
    )


settings = load_settings()
