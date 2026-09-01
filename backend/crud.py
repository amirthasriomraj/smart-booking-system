from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy import desc

from fastapi import HTTPException

from models import User, Booking, UserProfile, RefreshToken, PlatformCustomer, BusinessCustomer
from auth import hash_password, verify_password, validate_password, generate_refresh_token, hash_refresh_token

import secrets
import hashlib
from datetime import datetime, timedelta
from config import get_settings

settings = get_settings()

# -------------------------
# USER CRUD
# -------------------------

def create_user(db: Session, username: str, email: str, password: str):
    validate_password(password)

    existing_user = db.query(User).filter(
        or_(User.username == username, User.email == email)
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Username or email already exists"
        )

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role="user"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Automatically create profile
    profile = UserProfile(user_id=user.id)
    db.add(profile)
    db.commit()

    return user


def deactivate_user(db: Session, user_id: int):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()
    db.refresh(user)

    return user


def activate_user(db: Session, user_id: int):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    db.commit()
    db.refresh(user)

    return user


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account inactive")

    return user


# -------------------------
# PROFILE CRUD
# -------------------------

def get_user_profile(db: Session, user_id: int):
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return profile


def update_user_profile(db: Session, user_id: int, profile_data):
    profile = get_user_profile(db, user_id)

    if profile_data.first_name is not None:
        profile.first_name = profile_data.first_name

    if profile_data.last_name is not None:
        profile.last_name = profile_data.last_name

    if profile_data.phone is not None:
        profile.phone = profile_data.phone

    db.commit()
    db.refresh(profile)

    return profile


# NOTE: the legacy flat-model booking CRUD (create/get/list/update/delete
# against the pre-Milestone-7 `Booking(date, time, user_id)` shape) has been
# removed. Milestone 7 replaces it with `crud_booking.py`, operating on the
# new tenant-aware `Booking` model (see models.py and IMPLEMENTATION_PLAN.md
# M7 scope bullet 1).


# -------------------------
# ADMIN USER MANAGEMENT
# -------------------------

def get_all_users(db: Session):
    return db.query(User).all()


def delete_user(db: Session, user_id: int):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check bookings (Milestone 7: Booking no longer has a direct user_id
    # column — a user can be attached to a booking either as the staff
    # member who created it, or, via PlatformCustomer -> BusinessCustomer,
    # as the customer it was booked for).
    bookings_exist = (
        db.query(Booking.id)
        .outerjoin(BusinessCustomer, Booking.customer_id == BusinessCustomer.id)
        .outerjoin(PlatformCustomer, BusinessCustomer.platform_customer_id == PlatformCustomer.id)
        .filter(or_(Booking.created_by == user_id, PlatformCustomer.user_id == user_id))
        .first()
    )

    if bookings_exist:
        raise HTTPException(
            status_code=409,
            detail="User has existing bookings. Deactivate instead."
        )

    db.delete(user)
    db.commit()

    return {"detail": "User deleted successfully"}


# -------------------------
# PASSWORD RESET
# -------------------------

def generate_reset_token():
    return secrets.token_urlsafe(32)


def hash_token(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def create_password_reset_token(db: Session, email: str):
    user = db.query(User).filter(User.email == email).first()

    # Always return generic response
    if not user:
        return

    raw_token = generate_reset_token()
    token_hash = hash_token(raw_token)

    user.reset_token_hash = token_hash
    user.reset_token_expiry = datetime.utcnow() + timedelta(minutes=15)

    db.commit()

    return raw_token  # This would normally be emailed


def reset_password(db: Session, token: str, new_password: str):
    token_hash = hash_token(token)

    user = db.query(User).filter(
        User.reset_token_hash == token_hash
    ).first()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    if not user.reset_token_expiry or user.reset_token_expiry < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    validate_password(new_password)

    user.hashed_password = hash_password(new_password)

    # Invalidate token
    user.reset_token_hash = None
    user.reset_token_expiry = None

    db.commit()

    return {"detail": "Password reset successful"}


# -------------------------
# REFRESH TOKEN MANAGEMENT
# -------------------------

def create_refresh_token(db: Session, user_id: int):
    raw_token = generate_refresh_token()
    token_hash = hash_refresh_token(raw_token)

    expires_at = datetime.utcnow() + timedelta(days=7)

    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at
    )

    db.add(refresh_token)
    db.commit()

    return raw_token


def rotate_refresh_token(db: Session, raw_token: str):
    token_hash = hash_refresh_token(raw_token)

    refresh_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # 🔥 Replay detection
    if refresh_token.revoked:
        # If token was already rotated, it's a replay attempt
        if refresh_token.replaced_by_token_id:
            # Invalidate entire user session chain
            db.query(RefreshToken).filter(
                RefreshToken.user_id == refresh_token.user_id
            ).update({"revoked": True})
            db.commit()

        raise HTTPException(status_code=401, detail="Refresh token revoked")

    if refresh_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh token expired")

    # 🔄 Rotation starts here

    # Generate new token
    new_raw_token = generate_refresh_token()
    new_token_hash = hash_refresh_token(new_raw_token)

    new_expires_at = datetime.utcnow() + timedelta(days=7)

    new_refresh_token = RefreshToken(
        user_id=refresh_token.user_id,
        token_hash=new_token_hash,
        expires_at=new_expires_at
    )

    db.add(new_refresh_token)
    db.commit()
    db.refresh(new_refresh_token)

    # Revoke old token
    refresh_token.revoked = True
    refresh_token.replaced_by_token_id = new_refresh_token.id

    db.commit()

    return refresh_token.user_id, new_raw_token


def revoke_refresh_token(db: Session, raw_token: str):
    token_hash = hash_refresh_token(raw_token)

    refresh_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    refresh_token.revoked = True
    db.commit()

    return {"detail": "Logged out successfully"}


def revoke_all_refresh_tokens(db: Session, user_id: int):
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked == False
    ).update({"revoked": True})

    db.commit()

    return {"detail": "Logged out from all devices"}