from __future__ import annotations

import functools
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_password: str = "changeme"
    secret_key: str = "dev-insecure-secret-key"
    fernet_key: str = ""  # base64 Fernet key; generated on the fly if empty (dev only)

    database_url: str = "postgresql+psycopg://smbcrawler:smbcrawler@db:5432/smbcrawler_ui"
    redis_url: str = "redis://redis:6379/0"

    data_dir: Path = Path("/data")
    scan_concurrency: int = 2

    session_cookie: str = "smbui_session"
    session_max_age: int = 60 * 60 * 12  # 12h

    @property
    def scans_dir(self) -> Path:
        return self.data_dir / "scans"

    def ensure_dirs(self) -> None:
        self.scans_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "xdg" / "smbcrawler").mkdir(parents=True, exist_ok=True)


@functools.lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s


settings = get_settings()
