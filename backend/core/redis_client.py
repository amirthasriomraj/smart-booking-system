import redis
from config import get_settings

settings = get_settings()

redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)