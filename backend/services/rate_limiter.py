from fastapi import HTTPException, Request
from core.redis_client import redis_client

def rate_limit(max_requests: int, window_seconds: int):
    def dependency(request: Request):
        client_ip = request.client.host
        path = request.url.path

        key = f"rate_limit:{client_ip}:{path}"

        try:
            current_count = redis_client.incr(key)

            print("RATE LIMIT:", key, current_count)

            if current_count == 1:
                redis_client.expire(key, window_seconds)

            if current_count > max_requests:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests"
                )

        except HTTPException:
            # ✅ IMPORTANT: let FastAPI handle it
            raise

        except Exception as e:
            # Redis failure → fail open
            print("REDIS ERROR:", e)

    return dependency