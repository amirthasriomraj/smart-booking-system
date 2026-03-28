from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Time,
    ForeignKey,
    UniqueConstraint,
    Boolean,
    DateTime,
    Index
)
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # Authentication
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    # Authorization
    role = Column(String, default="user", nullable=False)

    # Account status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Password reset
    reset_token_hash = Column(String, nullable=True)
    reset_token_expiry = Column(DateTime, nullable=True)

    # One-to-one relationship
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete")

    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    profile_image_url = Column(String, nullable=True)
    document_url = Column(String, nullable=True)

    user = relationship("User", back_populates="profile")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)

    date = Column(Date, nullable=False, index=True)
    time = Column(Time, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("date", "time", name="unique_booking_slot"),
        Index("idx_booking_user_date", "user_id", "date"),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    token_hash = Column(String, nullable=False, unique=True)

    expires_at = Column(DateTime, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    revoked = Column(Boolean, default=False, nullable=False)

    replaced_by_token_id = Column(Integer, ForeignKey("refresh_tokens.id"), nullable=True)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    replaced_by = relationship("RefreshToken", remote_side=[id])