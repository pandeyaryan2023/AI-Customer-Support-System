from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env  (config.py is backend/app/core/config.py)
BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Application settings, read from environment variables or backend/.env."""

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cors_origins: str = (
        "http://localhost:5500,http://127.0.0.1:5500,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )

    # Knowledge-base uploads. Kept OUTSIDE frontend/, which is publicly served at /app/.
    storage_dir: Path = BACKEND_DIR / "storage" / "documents"
    max_upload_mb: int = 10

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
