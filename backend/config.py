from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Smart Booking & Notification Backend System"
    DEBUG: bool = True  # Default for dev

    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # Frontend (used to build links in outgoing emails — password reset,
    # staff invitations. Must be the app's actual origin, i.e. wherever
    # nginx proxies /api to this backend — never the Vite dev server port.)
    FRONTEND_BASE_URL: str = "http://localhost"

    # SMTP - Email
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    EMAIL_FROM: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()