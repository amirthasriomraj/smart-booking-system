from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    Time,
    ForeignKey,
    UniqueConstraint,
    Boolean,
    DateTime,
    Index,
    text,
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


# -------------------------
# TENANT FOUNDATION (Milestone 1)
# Frozen RBAC / registration model — TAS Part 3 §2, §3, §5, §10
# -------------------------

class Role(Base):
    """Master table of platform roles (TAS Part 3 §2)."""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)

    code = Column(String, unique=True, nullable=False, index=True)  # e.g. PLATFORM_ADMIN
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)


class UserRole(Base):
    """Platform-scoped role assignment (e.g. Platform Administrator, Customer)."""
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Country(Base):
    """Master table of countries (TAS Part 3 §3)."""
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True, index=True)

    iso_code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    currency_code = Column(String, nullable=True)
    timezone = Column(String, nullable=True)


class BusinessCategory(Base):
    """Master table of business categories (PRD §12 Step 1)."""
    __tablename__ = "business_categories"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)


class Business(Base):
    """
    Represents a tenant (TAS Part 3 §3).

    Status values follow the frozen lifecycle (PRD §13 / TAS §3):
    Pending -> Active -> Suspended, or Pending -> Rejected.
    """
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, index=True)

    business_name = Column(String, nullable=False, index=True)
    business_category_id = Column(Integer, ForeignKey("business_categories.id"), nullable=False)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)  # BR-006
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)

    status = Column(String, nullable=False, default="Pending", index=True)

    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class BusinessMember(Base):
    """
    Business-scoped role assignment (TAS Part 3 §5).

    Used for Business Owner / Branch Manager / HR User. The Business Owner's
    membership row is created at registration time, alongside the Pending
    business record — approval activates the business, it does not create
    the ownership relationship.

    Milestone 3 (Employee/Staff Invitation & Onboarding) adds invitation
    state directly to this table rather than a new Invitation entity
    (IMPLEMENTATION_DECISIONS.md ID-005): the token belongs to a specific
    membership, not to the User identity. `requires_credential_setup` is
    recorded explicitly at invite time and never re-derived from
    `User.is_active` at acceptance (ID-005). `invited_branch_id` is a
    temporary staging field for a pending Branch Manager invitation's target
    branch — the real `BranchAssignment` row is only created on acceptance
    (ID-010), and this field is cleared once that happens.
    """
    __tablename__ = "business_members"

    id = Column(Integer, primary_key=True, index=True)

    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)

    status = Column(String, nullable=False, default="Active")

    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    left_at = Column(DateTime, nullable=True)

    # Milestone 3 — invitation lifecycle (ID-005, ID-009, ID-010)
    invitation_token_hash = Column(String, nullable=True, index=True)
    invitation_token_expiry = Column(DateTime, nullable=True)
    requires_credential_setup = Column(Boolean, nullable=False, default=False)
    invited_branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("business_id", "user_id", name="uq_business_member_business_user"),
    )


class AuditLog(Base):
    """
    Immutable, append-only audit trail (TAS Part 3 §10 / PRD §30).
    No update or delete path is exposed anywhere in the application.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=True, index=True)
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(Integer, nullable=False)
    action = Column(String, nullable=False, index=True)

    previous_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    performed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


# -------------------------
# BRANCH (Milestone 2)
# Frozen Branch model — TAS Part 3 §4, §5; PRD §12 Step 5, §13
# -------------------------

class Branch(Base):
    """
    Represents a branch of a Business (TAS Part 3 §4).

    Status is split into two independent fields (an approved deviation
    from the TAS's single `status` column, see Milestone 2 plan):
    - approval_status: Platform-Admin-controlled (Pending -> Approved/Rejected).
    - is_active: Business-Owner-controlled, only togglable once Approved.
      Deactivating a branch does not erase the fact that it was approved.
    """
    __tablename__ = "branches"

    id = Column(Integer, primary_key=True, index=True)

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)

    branch_name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True, index=True)
    state = Column(String, nullable=True)
    postal_code = Column(String, nullable=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)

    approval_status = Column(String, nullable=False, default="Pending", index=True)
    is_active = Column(Boolean, nullable=False, default=False)

    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class BranchWorkingHours(Base):
    """Per-weekday operating hours for a branch (TAS Part 3 §4)."""
    __tablename__ = "branch_working_hours"

    id = Column(Integer, primary_key=True, index=True)

    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)

    weekday = Column(Integer, nullable=False)  # 0=Monday .. 6=Sunday
    opening_time = Column(Time, nullable=True)
    closing_time = Column(Time, nullable=True)
    is_closed = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("branch_id", "weekday", name="uq_branch_working_hours_branch_weekday"),
    )


class BranchAssignment(Base):
    """
    Tracks Branch Manager (and future branch-linked Resource User) transfers
    without losing history (TAS Part 3 §5). No endpoint writes to this table
    yet — it lands with the Employee/Staff Invitation milestone. HR Users are
    business-scoped in V1 and never get a row here (Milestone 2 deviation).
    """
    __tablename__ = "branch_assignments"

    id = Column(Integer, primary_key=True, index=True)

    business_member_id = Column(Integer, ForeignKey("business_members.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)

    assigned_from = Column(DateTime, default=datetime.utcnow, nullable=False)
    assigned_to = Column(DateTime, nullable=True)
    is_current = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index(
            "uq_branch_assignments_one_current",
            "business_member_id",
            unique=True,
            postgresql_where=text("is_current = true"),
            # SQLite (used for the test suite's Base.metadata.create_all — see
            # tests/conftest.py) silently drops postgresql_where and would
            # otherwise create a full unique index on business_member_id,
            # wrongly forbidding a second (historical) row for the same
            # member. Only surfaced in Milestone 3, the first code to write a
            # second BranchAssignment row. Production Postgres is unaffected
            # — its DDL comes from the Alembic migration, not this line.
            sqlite_where=text("is_current = true"),
        ),
    )