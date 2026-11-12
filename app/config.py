"""
Uygulama konfigürasyonu - environment variables
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Veritabani (Coolify Supabase ic ag)
    database_url: str = "postgresql://postgres:postgres@supabase-db:5432/postgres"

    # Supabase Auth
    supabase_url: str = ""
    supabase_internal_url: str = ""
    supabase_key: str = ""
    supabase_jwt_secret: str = ""

    app_name: str = "Bet Data Panel"
    debug: bool = False

    allowed_origins: str = ""

    cookie_secure: bool = True
    login_max_attempts: int = 5
    login_window_seconds: int = 300

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def supabase_base_urls(self) -> list[str]:
        """Auth dogrulama icin denenecek taban URL'ler: once ic ag, sonra public."""
        urls = []
        if self.supabase_internal_url:
            urls.append(self.supabase_internal_url.rstrip("/"))
        if self.supabase_url:
            u = self.supabase_url.rstrip("/")
            if u not in urls:
                urls.append(u)
        return urls

    @field_validator("database_url")
    @classmethod
    def fix_postgres_url(cls, v: str) -> str:
        if v and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
