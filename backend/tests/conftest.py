import os
import smtplib
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


# Fake SMTP for tests — email_service.py always calls smtplib.SMTP(host, port)
# as a context manager, so tests otherwise attempt a real network connection
# to the fake SMTP_HOST above and hang until socket timeout on every
# notification-triggering test. This never touches a network.
class FakeSMTP:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def starttls(self, *args, **kwargs):
        pass

    def login(self, *args, **kwargs):
        pass

    def send_message(self, *args, **kwargs):
        pass


smtplib.SMTP = FakeSMTP


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)