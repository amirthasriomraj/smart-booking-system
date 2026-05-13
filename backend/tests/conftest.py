import os
import pytest

# Test environment
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["REDIS_URL"] = "redis://localhost:6379"

os.environ["SMTP_HOST"] = "smtp.test.com"
os.environ["SMTP_PORT"] = "587"
os.environ["SMTP_USER"] = "test@test.com"
os.environ["SMTP_PASSWORD"] = "test-password"
os.environ["EMAIL_FROM"] = "test@test.com"

from database import Base, engine
from services import rate_limiter


# Fake Redis for tests
class FakeRedis:
    def incr(self, key):
        return 1

    def expire(self, key, seconds):
        pass


# Override real Redis
rate_limiter.redis_client = FakeRedis()


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)