import time
import logging
from database import Base, engine
from routers import bookings, auth, profiles, users
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware

from core.logging_config import setup_logging
setup_logging()

from config import get_settings
settings = get_settings()

app = FastAPI(debug=settings.DEBUG)

if settings.DEBUG:
    origins = ["*"]     # DEV
else:
    origins = []        # PROD (same-origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger = logging.getLogger("request")

@app.middleware("http")
async def logging_middleware(request: Request, call_next):

    start_time = time.time()

    response = await call_next(request)

    process_time = (time.time() - start_time) * 1000
    formatted_time = f"{process_time:.2f}ms"

    method = request.method
    path = request.url.path
    status_code = response.status_code
    client_ip = request.client.host

    logger.info(
        f"[REQUEST] {method} {path} | "
        f"Status: {status_code} | "
        f"Time: {formatted_time} | "
        f"IP: {client_ip}"
    )

    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)

    # Prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # Enforce HTTPS in production
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.status_code,
                "type": exc.__class__.__name__,
                "message": exc.detail
            }
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": 422,
                "type": "ValidationError",
                "message": exc.errors() if settings.DEBUG else "Invalid request payload."
            }
        }
    )

@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={
            "success": False,
            "error": {
                "code": 409,
                "type": "IntegrityError",
                "message": str(exc.orig) if settings.DEBUG else "Database constraint violation."
            }
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": 500,
                "type": type(exc).__name__ if settings.DEBUG else "ServerError",
                "message": str(exc) if settings.DEBUG else "An unexpected error occurred."
            }
        }
    )


app.include_router(auth.router, prefix="/api/v1")
app.include_router(bookings.router, prefix="/api/v1")
app.include_router(profiles.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")

@app.get("/")
def health_check():
    return {"status": "Backend is running"}
