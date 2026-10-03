from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://scadenzario:scadenzario@localhost:5432/scadenzario"

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 90

    OCR_WORKERS: int = 2
    TZ: str = "Europe/Madrid"

    BREVO_API_KEY: str = ""
    NOTIFY_EMAIL_FROM: str = "scadenzario@example.com"

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # vedi services/image_storage.py — oggi solo "local" è implementato, il resto del
    # codice parla solo con l'interfaccia ImageStorage per rendere una futura
    # migrazione a S3/cloud un cambio isolato a quel modulo.
    IMAGE_STORAGE_BACKEND: str = "local"
    IMAGE_STORAGE_DIR: str = "app/data/product_images"


settings = Settings()
