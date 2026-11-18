from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SUJAAI WhatsApp Campaign Manager"
    app_env: str = "production"
    api_prefix: str = "/api"

    # Supply these values through deployment environment variables.
    database_url: str
    secret_key: str
    admin_email: str = ""
    admin_password: str = ""

    access_token_expire_minutes: int = 720
    cors_origins: str = "https://sujaai.vercel.app"
    # Vercel's deployed filesystem is read-only except for /tmp.
    # Use Cloudinary for durable campaign image storage.
    upload_dir: str = "/tmp/sujaai-uploads"
    max_upload_mb: int = 8

    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_graph_api_version: str = "v26.0"
    whatsapp_verify_token: str = ""
    meta_app_secret: str = ""

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def whatsapp_configured(self) -> bool:
        return bool(self.whatsapp_access_token and self.whatsapp_phone_number_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
