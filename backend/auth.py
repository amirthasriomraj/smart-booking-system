from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException
from typing import Optional
import re
import secrets
import hashlib

from config import get_settings
settings = get_settings()

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# -----------------------------
# Password Utilities
# -----------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def validate_password(password: str):
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must contain a uppercase letter")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must contain a lowercase letter")
    if not re.search(r"[0-9]", password):
        raise HTTPException(status_code=400, detail="Password must contain a number")


# -----------------------------
# Access Token (Short-lived, Stateless)
# -----------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# -----------------------------
# Refresh Token (Stateful)
# -----------------------------

def generate_refresh_token() -> str:
    """
    Generate a secure random refresh token.
    """
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """
    Hash refresh token before storing in database.
    """
    return hashlib.sha256(token.encode()).hexdigest()


# -----------------------------
# CSRF Token Utility (NEW)
# -----------------------------

def generate_csrf_token() -> str:
    """
    Generate CSRF token used for double-submit cookie protection.
    """
    return secrets.token_hex(16)