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

    # Celery (Milestone 8 — ID-049: background/scheduled-job foundation for
    # balance reminders, the 48-hour balance-deadline sweep, and expired-hold
    # cleanup). Defaults point at the same Redis instance as REDIS_URL; set
    # explicitly in .env if broker/result-backend should differ from it.
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Razorpay (Milestone 8 — ID-055). Empty defaults so Settings() does not
    # fail to construct (e.g. in tests, or before credentials are issued);
    # real values are required before any live Razorpay call is made in a
    # later M8 phase. Never commit real values — see backend/env.example.
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    RAZORPAY_MODE: str = "test"  # test | live — must not assume production Route eligibility (ID-055)

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()