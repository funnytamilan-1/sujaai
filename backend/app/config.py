from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "SUJAAI WhatsApp Campaign Manager"
    app_env: str = "development"
    api_prefix: str = "/api"
    database_url: str = "postgresql://neondb_owner:npg_WKlRV28CiQpz@ep-empty-tooth-bbwpkbh3.c-15.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    secret_key: str = "sujai28uee3=0r4rrt5gog'isydfuwfrfoprefgwfo4r[epe4l3[edhygdsc5uqwgea7hteduyesgsftuiebehehiedhdhd"
    admin_email: str = "adminsuja@gmail.com"
    admin_password: str = "sujai10142027"
    access_token_expire_minutes: int = 720
    cors_origins: str = "https://sujaai.vercel.app/"
    upload_dir: str = "uploads"
    max_upload_mb: int = 8
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_graph_api_version: str = "v26.0"
    whatsapp_verify_token: str = ""
    meta_app_secret: str = ""
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

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
