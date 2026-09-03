from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    Time,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    Boolean,
    DateTime,
    Index,
    JSON,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base

# Structured JSON storage: real JSONB on PostgreSQL, plain JSON on SQLite
# (the test suite's Base.metadata.create_all dialect — see tests/conftest.py).
JSONVariant = JSONB().with_variant(JSON(), "sqlite")


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
    """
    1:1 person profile for every User (staff and Customer alike).

    Milestone 6 (ID-029) extends this table with the PRD §17.2 Customer
    Personal/Contact/Address Information fields (gender, date_of_birth,
    address_line, city, state, country_id, postal_code) — none of those
    fields exist anywhere in the TAS §6 PlatformCustomer/BusinessCustomer
    schema. Reusing this existing 1:1 table avoids a second
    first_name/last_name field on PlatformCustomer.
    """
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

    # Milestone 6 (ID-029)
    gender = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    address_line = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=True)
    postal_code = Column(String, nullable=True)

    user = relationship("User", back_populates="profile")


# NOTE: the pre-Milestone-7 flat `Booking` model (date/time/user_id only,
# no business/branch/service/resource linkage, admin hard-delete endpoint)
# is replaced below by the Milestone 7 Booking Engine schema
# (IMPLEMENTATION_PLAN.md M7 scope bullet 1: "Replace/generalize the legacy
# booking structure as required by V1"). See the Milestone 7 section further
# down this file for the new `Booking` / `BookingHistory` models.


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

    # Milestone 4 — Resource User invitation staging (ID-014). Mirrors
    # invited_branch_id: stages which Resource a pending Resource User
    # invitation belongs to; cleared once Resource.linked_user_id is set on
    # acceptance.
    linked_resource_id = Column(Integer, ForeignKey("resources.id"), nullable=True)

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


# -------------------------
# RESOURCE MANAGEMENT (Milestone 4)
# TAS Part 3 §7; PRD §14.1-14.6
# -------------------------

class ResourceCategory(Base):
    """Business-defined grouping of resources (TAS Part 3 §7; PRD §14.2)."""
    __tablename__ = "resource_categories"

    id = Column(Integer, primary_key=True, index=True)

    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)

    category_name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Resource(Base):
    """
    Generic Resource — anything reservable/assignable to perform a service
    (TAS Part 3 §7; PRD §14.1-14.5).

    `business_id` is denormalized from `branch.business_id` at creation and
    is not independently mutable (ID-012 — resolves a TAS §7/business_id-list
    inconsistency; not present in the TAS §7 column list itself).

    `max_bookings_per_day` / `booking_buffer_minutes` are V1-mandatory
    (PRD §14.3) storage-only attributes added here; enforcement against
    actual bookings is Milestone 7 scope (ID-013).

    `linked_user_id` is populated only once a `requires_login = true`
    Resource's invited Resource User accepts (ID-014); it stays NULL for a
    Resource that never requires login.
    """
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)

    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)  # ID-012
    resource_category_id = Column(Integer, ForeignKey("resource_categories.id"), nullable=False, index=True)
    linked_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    resource_name = Column(String, nullable=False)
    code = Column(String, nullable=True)
    description = Column(String, nullable=True)

    status = Column(String, nullable=False, default="Pending", index=True)
    requires_login = Column(Boolean, nullable=False, default=False)

    # V1-mandatory scheduling/configuration attributes not in the TAS §7
    # Resources column list (ID-013). Storage only in Milestone 4.
    max_bookings_per_day = Column(Integer, nullable=True)
    booking_buffer_minutes = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ResourceWorkingHours(Base):
    """
    Per-weekday hours overriding inherited branch hours (TAS Part 3 §7).

    `break_start_time` / `break_end_time` (one break window per weekday row)
    are V1-mandatory (PRD §14.3 "Break Timings") columns not in the TAS §7
    Resource Working Hours column list; storage only in Milestone 4 (ID-013).
    """
    __tablename__ = "resource_working_hours"

    id = Column(Integer, primary_key=True, index=True)

    resource_id = Column(Integer, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)

    weekday = Column(Integer, nullable=False)  # 0=Monday .. 6=Sunday
    opening_time = Column(Time, nullable=True)
    closing_time = Column(Time, nullable=True)
    is_closed = Column(Boolean, nullable=False, default=False)
    break_start_time = Column(Time, nullable=True)
    break_end_time = Column(Time, nullable=True)

    __table_args__ = (
        UniqueConstraint("resource_id", "weekday", name="uq_resource_working_hours_resource_weekday"),
    )


# -------------------------
# SERVICE MANAGEMENT (Milestone 5)
# TAS Part 3 §8; PRD §15.1-15.6
# -------------------------

class ServiceTemplate(Base):
    """
    Business-level master service definition (TAS Part 3 §8; PRD §15.1).

    `business_id` is the direct owner (ID-024 — not present in the TAS §8
    column list itself, resolving the same business_id inconsistency ID-012
    already resolved for Resource).

    Create-once: no general update endpoint exists for name/description/
    duration/price/etc. after creation (ID-019 — "Templates remain
    immutable"). Only `status` (Active/Inactive) is ever toggled after
    creation.

    `default_buffer_minutes` / `default_working_rules` are V1-mandatory
    (PRD §15.1) storage-only attributes not in the TAS §8 column list
    (ID-025). `default_working_rules` is deliberately opaque — no internal
    structure or enforcement is defined or built in Milestone 5.
    """
    __tablename__ = "service_templates"

    id = Column(Integer, primary_key=True, index=True)

    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)  # ID-024

    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    default_duration = Column(Integer, nullable=False)
    default_price = Column(Numeric(10, 2), nullable=False)

    # V1-mandatory fields not in the TAS §8 Service Templates column list (ID-025).
    default_buffer_minutes = Column(Integer, nullable=True)
    default_working_rules = Column(JSONVariant, nullable=True)

    status = Column(String, nullable=False, default="Active", index=True)  # ID-019: Active / Inactive only

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ServiceTemplateResourceCategory(Base):
    """Default Resource Categories for a Service Template (PRD §15.1, §15.6)."""
    __tablename__ = "service_template_resource_categories"

    id = Column(Integer, primary_key=True, index=True)

    service_template_id = Column(Integer, ForeignKey("service_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_category_id = Column(Integer, ForeignKey("resource_categories.id"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint(
            "service_template_id", "resource_category_id",
            name="uq_service_template_resource_category",
        ),
    )


class BranchService(Base):
    """
    Branch-specific implementation of a Service Template (TAS Part 3 §8;
    PRD §15.2-15.4).

    Always references a Service Template — there is no template-less Branch
    Service (ID-018). `business_id` is denormalized from `branch.business_id`
    at creation and is not independently mutable (ID-024).

    `status` is a 5-value lifecycle with no separate "Active" state —
    `Approved` is itself the live/bookable state (ID-020). `duration`/
    `price` are always the current *effective* configuration; a pending
    override's proposed values live only on `ServiceApproval` (ID-021).
    `pending_approval` is a separate boolean (TAS §8), true while a
    submitted override awaits a Business Owner decision.
    """
    __tablename__ = "branch_services"

    id = Column(Integer, primary_key=True, index=True)

    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)  # ID-024
    service_template_id = Column(Integer, ForeignKey("service_templates.id"), nullable=False, index=True)  # ID-018

    duration = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)

    status = Column(String, nullable=False, default="Approved", index=True)  # ID-020
    pending_approval = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("branch_id", "service_template_id", name="uq_branch_service_branch_template"),
    )


class BranchServiceResourceCategory(Base):
    """
    Live/effective Resource Category assignment for a Branch Service
    (PRD §15.6). Branch-overridable, independent of the Service Template's
    default assignment (ServiceTemplateResourceCategory).
    """
    __tablename__ = "branch_service_resource_categories"

    id = Column(Integer, primary_key=True, index=True)

    branch_service_id = Column(Integer, ForeignKey("branch_services.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_category_id = Column(Integer, ForeignKey("resource_categories.id"), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint(
            "branch_service_id", "resource_category_id",
            name="uq_branch_service_resource_category",
        ),
    )


class ServiceApproval(Base):
    """
    Tracks Branch Service override approvals (TAS Part 3 §8; PRD §15.4,
    §25.5). `previous_configuration` / `proposed_configuration` are
    structured JSONB snapshots (ID-021) — not in the TAS §8 column list —
    holding {duration, price, resource_category_ids} so the record remains
    a complete historical account after the decision, while BranchService
    itself only ever holds the current effective configuration.
    """
    __tablename__ = "service_approvals"

    id = Column(Integer, primary_key=True, index=True)

    branch_service_id = Column(Integer, ForeignKey("branch_services.id", ondelete="CASCADE"), nullable=False, index=True)

    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    decision = Column(String, nullable=False, default="Pending", index=True)  # Pending / Approved / Rejected

    previous_configuration = Column(JSONVariant, nullable=False)  # ID-021
    proposed_configuration = Column(JSONVariant, nullable=False)  # ID-021

    comments = Column(Text, nullable=True)
    decided_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# -------------------------
# CUSTOMER MANAGEMENT (Milestone 6)
# TAS Part 3 §6; PRD §17.1-17.6
# -------------------------

class PlatformCustomer(Base):
    """
    A Customer's platform identity (TAS Part 3 §6), 1:1 with User.

    One PlatformCustomer may have many BusinessCustomer relationship rows —
    one per business it has interacted with (ID-028: the TAS §6
    PlatformCustomer/BusinessCustomer split is authoritative over PRD
    §10.6/§11's contradictory "isolated per business" language, consistent
    with BR-039). Personal/contact/address fields live on the linked User's
    UserProfile (ID-029), not here — this table stays TAS-literal.
    """
    __tablename__ = "platform_customers"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    preferred_language = Column(String, nullable=True)
    preferred_timezone = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BusinessCustomer(Base):
    """
    The relationship between a PlatformCustomer and a specific Business
    (TAS Part 3 §6).

    `platform_customer_id` is NOT NULL — every Customer, including a
    staff-created walk-in with no immediate login, always has a backing
    PlatformCustomer/User, created via the ID-005 placeholder-credential
    mechanism when no existing identity is reused (ID-030, ID-031).

    `customer_number` is system-generated as `CUST-{id:06d}` via the
    existing flush-then-read-PK pattern (ID-033), not a per-business
    sequence. `status` (Active/Inactive/Archived-future, PRD §17.3) is
    per-business only; the linked User's `is_active` remains the
    independent platform-account-lock flag (ID-002/ID-008 precedent).

    No branch_id: Customer is a business-scoped entity, not branch-scoped
    (ID-032) — both Business Owner and Branch Manager get business-wide
    Customer Management authority.
    """
    __tablename__ = "business_customers"

    id = Column(Integer, primary_key=True, index=True)

    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    platform_customer_id = Column(
        Integer, ForeignKey("platform_customers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    customer_number = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="Active", index=True)

    first_visit_at = Column(DateTime, nullable=True)
    last_visit_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("business_id", "platform_customer_id", name="uq_business_customer_business_platform_customer"),
        UniqueConstraint("business_id", "customer_number", name="uq_business_customer_business_customer_number"),
    )


# -------------------------
# BOOKING MANAGEMENT (Milestone 7)
# TAS Part 3 §9; PRD §16, §18-24
# -------------------------

class Booking(Base):
    """
    Core transactional booking record (TAS Part 3 §9; PRD §18.2).

    Every Booking belongs to exactly one Business, Branch, Customer, Service
    (BranchService — the branch-specific, currently-effective implementation
    of a Service Template, not the template itself) and Resource (BR-042).
    `status` is a 3-value V1 lifecycle: Confirmed / Completed / Cancelled
    (PRD §18.5) — bookings are never deleted (BR-045).

    `cancellation_reason` / `completed_at` are not in the TAS §9 column list
    (ID-036): the former holds PRD §20's optional cancellation reason, the
    latter PRD §18.7's completion timestamp.

    The `(resource_id, booking_date, start_time)` uniqueness is the TAS §9
    constraint, kept as a defense-in-depth backstop — but as a *partial*
    unique index excluding Cancelled rows, since a cancelled booking
    releases the resource (PRD §20) and must not permanently block that
    slot from being rebooked. True overlap detection (covering differing
    booking durations and `Resource.booking_buffer_minutes` padding) is
    enforced in `crud_booking.py` application logic, not by this index
    alone (ID-037).
    """
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("business_customers.id"), nullable=False, index=True)
    branch_service_id = Column(Integer, ForeignKey("branch_services.id"), nullable=False, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False, index=True)

    booking_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    status = Column(String, nullable=False, default="Confirmed", index=True)  # Confirmed / Completed / Cancelled
    cancellation_reason = Column(Text, nullable=True)  # ID-036
    completed_at = Column(DateTime, nullable=True)  # ID-036

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        # Partial index, not a plain UniqueConstraint: a Cancelled booking
        # releases the resource (PRD §20) and must not permanently block its
        # exact resource/date/start_time from being rebooked, even though
        # the row itself is never deleted (BR-045). Mirrors the
        # BranchAssignment partial-index pattern above.
        Index(
            "uq_booking_resource_date_start_time",
            "resource_id", "booking_date", "start_time",
            unique=True,
            postgresql_where=text("status != 'Cancelled'"),
            sqlite_where=text("status != 'Cancelled'"),
        ),
    )


class BookingHistory(Base):
    """
    Immutable Booking history (TAS Part 3 §9; PRD §22). No update or delete
    path is exposed anywhere in the application, same as `AuditLog`.

    `previous_state` / `new_state` are structured JSONB snapshots (e.g.
    `{booking_date, start_time, end_time, resource_id, status}`), mirroring
    `ServiceApproval`'s existing snapshot pattern, so a single reschedule
    entry can show both the date and resource change together in one record
    (PRD §19.3's worked example shows exactly this).

    `performed_by` is nullable (Milestone 8 Phase 5-7 addition, ID-048):
    NULL represents the system actor for the automatic 48-hour
    balance-default cancellation — the platform's first
    system-triggered lifecycle transition, which by definition has no
    human user to attribute it to. Every other action (Created,
    Rescheduled, ResourceReassigned, Cancelled by a person, Completed)
    continues to always supply a real user id. Mirrors the nullable
    `AuditLog.performed_by` above, which already exists for the same
    system-action reason.
    """
    __tablename__ = "booking_history"

    id = Column(Integer, primary_key=True, index=True)

    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)

    action = Column(String, nullable=False)  # Created / Rescheduled / ResourceReassigned / Cancelled / Completed
    previous_state = Column(JSONVariant, nullable=True)
    new_state = Column(JSONVariant, nullable=True)

    performed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    performed_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# -------------------------
# PAYMENTS, FINANCIAL POLICIES & PROMOTIONS (Milestone 8)
# ID-044-ID-056 (docs/IMPLEMENTATION_DECISIONS.md) — M8 promotes Online
# Payments, Deposits, Refunds, Coupons/Promotions and the associated
# override/approval workflows from the frozen PRD/TAS's Version 2/deferred
# scope into V1 (ID-044). No frozen PRD/TAS text is rewritten; these models
# and ID-044-ID-056 are the authoritative record of what changed and why.
#
# `relationship()` is deliberately not used anywhere below, consistent with
# every model from Branch (Milestone 2) onward — callers join explicitly in
# crud_*.py, the same convention Booking/BookingHistory/AuditLog already
# follow above.
#
# NOTE (Phase 1A -> Phase 1B): the PostgreSQL GiST exclusion constraints
# that give `bookings`/`booking_holds` true interval-overlap protection
# (defense-in-depth only — the authoritative check is the transaction-scoped
# advisory lock + application-level interval/buffer validation) are NOT
# declared in `__table_args__` below or added to the existing `Booking`
# model. `ExcludeConstraint` has no SQLite equivalent (unlike the
# dialect-conditional `postgresql_where`/`sqlite_where` trick ID-043 used
# for a plain partial index), so declaring it in ORM metadata would break
# `Base.metadata.create_all()` against the SQLite engine `tests/conftest.py`
# uses. It is added as hand-written, Postgres-only DDL in the Phase 1B
# migration instead, entirely outside `Base.metadata` — see the Phase 1A
# completion report for detail.
# -------------------------

class BookingHold(Base):
    """
    Temporary, database-authoritative checkout/payment hold (ID-046).

    Represents a customer- or staff-initiated checkout in progress. A hold
    is a separate entity from `Booking` — it is never a provisional
    `Confirmed` booking (ID-046) and, for Reserve Without Payment, no hold
    is created at all (that flow goes straight to a normal `Booking` with
    no expiry; see `BookingFinancial.financial_status`).

    Availability = eligible resource interval - active Bookings - active
    unexpired BookingHolds. A hold must occupy the same slot-uniqueness
    space a Booking does; concurrency safety is provided by a
    transaction-scoped `pg_advisory_xact_lock(resource_id, date_key)`
    around the check-then-insert sequence in `crud_booking.py`/the M8
    checkout code (the authoritative mechanism), with the GiST exclusion
    constraint below as a same-table defense-in-depth backstop only — it
    does not by itself prevent a `Booking` from overlapping a `BookingHold`
    (constraints don't span tables).

    `price_snapshot` holds the ID-054 checkout-terms snapshot (calculated
    price, base/final overrides, coupon, discount, final amount, deposit
    percentage/amount due, platform fee rate, resource, interval, currency)
    captured at hold creation and left untouched for the hold's lifetime,
    even if configuration changes elsewhere while it is Active. An Active
    hold whose snapshot references a coupon also functions as that coupon's
    concurrency-safe usage reservation (see `Coupon`/`CouponRedemption`
    below) — no separate reservation table is needed.

    There is no `payment_id` column here: the in-progress payment attempt
    for a hold is found via `Payment.booking_hold_id` (the reverse lookup).
    A forward pointer here in addition to that would form a circular FK
    between `booking_holds` and `payments` — confirmed a real problem
    during Phase 1A verification (SQLAlchemy could not order
    `Base.metadata.drop_all()` without it), not merely a style choice.
    """
    __tablename__ = "booking_holds"

    id = Column(Integer, primary_key=True, index=True)

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    branch_service_id = Column(Integer, ForeignKey("branch_services.id"), nullable=False, index=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=False, index=True)
    # NOT NULL: every M8 checkout flow (customer self-checkout, staff
    # walk-in, staff email-link, staff external-manual) identifies/creates
    # the BusinessCustomer before a hold is created (mirroring
    # create_staff_booking/create_customer_booking's existing requirement),
    # so there is no flow where a hold's customer is genuinely unknown.
    customer_id = Column(Integer, ForeignKey("business_customers.id"), nullable=False, index=True)

    booking_date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    # CustomerCheckout / StaffWalkIn / StaffEmailLink / StaffExternalManual
    # (no ReserveWithoutPayment — RWP never creates a hold, ID-046 correction)
    hold_type = Column(String, nullable=False, index=True)
    # Active / Completed / Expired / Cancelled — only Active occupies availability
    status = Column(String, nullable=False, default="Active", index=True)

    expires_at = Column(DateTime, nullable=False, index=True)
    price_snapshot = Column(JSONVariant, nullable=False)  # ID-054

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        # Query-performance index only (find active holds for a resource/date
        # when computing availability or running the expiry sweep). True
        # overlap protection is the advisory lock + GiST exclusion DDL
        # described above, not this index.
        Index("ix_booking_holds_resource_date_status", "resource_id", "booking_date", "status"),
    )


class BookingFinancial(Base):
    """
    Per-booking financial state, kept deliberately separate from
    `Booking.status` (ID-045). `Booking.status` stays the existing V1
    three-value scheduling lifecycle (Confirmed/Completed/Cancelled); a
    booking's payment/deposit/balance position lives here instead, so a
    booking can be `Confirmed` while `financial_status` is e.g.
    "AwaitingBalance".

    `financial_status` values and transitions (see ID-045/ID-048/ID-051):
      (created) -> ReserveWithoutPayment   (RWP; terminal, no expiry/deadline)
      (created) -> AwaitingBalance         (deposit captured, balance outstanding)
      AwaitingBalance -> FullyPaid         (balance captured)
      AwaitingBalance -> BalanceDefaulted  (48h sweep, ID-048; paired with
                                             Booking.status -> Cancelled)
      (created) -> FullyPaid               (full payment captured at booking time)

    There is no "Refunded"/"PartiallyRefunded" status here or on `Payment`
    — a booking's refund position is the derived `amount_refunded` running
    total (updated when a `Refund` reaches `Completed`), independent of
    `financial_status`, so a `FullyPaid` booking that is later refunded
    stays `FullyPaid` (an accurate collection history) with
    `amount_refunded > 0` recording the return.

    `platform_fee_rate_snapshot` is the ID-051 per-booking fee-rate
    snapshot, set from the business's then-effective rate at the booking's
    first successful financial transaction and never re-read afterward.
    `base_price`/`base_price_override`/`final_price_override` mirror the
    frozen M8 calculation order (calculated -> base override -> coupon ->
    discounted amount -> final override -> final amount -> deposit calc);
    the coupon itself is `coupon_id`, and the full audit trail of each
    override lives on `BookingPriceAdjustment`, not here — this table only
    ever holds the current effective values, the same
    current-value-vs-history split already established by
    `BranchService`/`ServiceApproval` (ID-021).
    """
    __tablename__ = "booking_financials"

    id = Column(Integer, primary_key=True, index=True)

    # ondelete="CASCADE": a pure dependent record of one Booking, the same
    # relationship shape as the existing BookingHistory.booking_id.
    booking_id = Column(
        Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)

    total_amount = Column(Numeric(10, 2), nullable=False)
    amount_paid = Column(Numeric(10, 2), nullable=False, default=0)
    amount_refunded = Column(Numeric(10, 2), nullable=False, default=0)

    deposit_required = Column(Boolean, nullable=False, default=False)
    deposit_amount = Column(Numeric(10, 2), nullable=True)

    balance_due = Column(Numeric(10, 2), nullable=True)
    balance_due_at = Column(DateTime, nullable=True, index=True)  # NULL for ReserveWithoutPayment / FullyPaid
    balance_reminder_sent_at = Column(DateTime, nullable=True)

    # ReserveWithoutPayment / AwaitingBalance / FullyPaid / BalanceDefaulted
    financial_status = Column(String, nullable=False, index=True)

    platform_fee_rate_snapshot = Column(Numeric(5, 2), nullable=True)  # ID-051

    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=True, index=True)
    base_price = Column(Numeric(10, 2), nullable=False)
    base_price_override = Column(Numeric(10, 2), nullable=True)
    final_price_override = Column(Numeric(10, 2), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        # Serves both scheduled M8 sweeps directly: the 72h reminder scan
        # (financial_status='AwaitingBalance' AND balance_due_at in the
        # reminder window) and the 48h deadline sweep (same status AND
        # balance_due_at <= now). A composite index matches both filters in
        # one pass instead of two separate single-column indexes.
        Index("ix_booking_financials_status_balance_due_at", "financial_status", "balance_due_at"),
    )


class Payment(Base):
    """
    A single payment collection attempt/transaction (rule 23/27). Reused
    across full payment, deposit, balance payment, and reschedule
    price-difference collection (`payment_type`).

    `status` is a historical fact about this one collection attempt and is
    never rewritten by a later refund (Refund is the separately-authoritative
    record of money returned — see `Refund` below):
      Created -> Authorized -> Captured   (Authorized may be skipped for
                                            auto-capture or offline methods)
      Created / Authorized -> Failed

    Only `razorpay_order_id`/`razorpay_payment_id` (Razorpay's own
    identifiers) and `verified_at` (when server-side signature verification
    succeeded) are persisted for the online flow — the Razorpay checkout
    signature itself is verified once, server-side, and deliberately never
    stored (rule 26; no authentication/signature material at rest).
    Webhook-delivery idempotency is tracked separately on
    `RazorpayWebhookEvent`, not here.

    `cash_received`/`change_returned` hold the interactive cash-payment
    detail (business rule 12.A); `verified_by` records the staff member who
    confirmed a manual/external payment (business rule 12.C).
    `platform_fee_rate_snapshot`/`platform_fee_amount` are this specific
    transaction's proportional platform-fee earn (ID-051/rule 19);
    `gateway_fee_amount`/`gateway_fee_tax_amount` are populated only when
    reliably reported by Razorpay — never invented (ID-052).
    """
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    # ondelete="CASCADE": dependent record of one Booking once the booking
    # exists, matching BookingHistory.booking_id; NULL until the checkout
    # this payment belongs to actually produces a confirmed Booking.
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=True, index=True)
    booking_hold_id = Column(Integer, ForeignKey("booking_holds.id"), nullable=True, index=True)

    # Deposit / FullPayment / BalancePayment / RescheduleCollection
    # (no ReserveWithoutPayment — RWP moves no money; see BookingFinancial, ID-046 correction)
    payment_type = Column(String, nullable=False, index=True)
    # RazorpayOnline / Cash / ExternalManual
    method = Column(String, nullable=False, index=True)
    # Created / Authorized / Captured / Failed
    status = Column(String, nullable=False, default="Created", index=True)

    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String, nullable=False, default="INR")

    razorpay_order_id = Column(String, nullable=True, index=True)
    razorpay_payment_id = Column(String, nullable=True, index=True)
    verified_at = Column(DateTime, nullable=True)  # replaces persisting the checkout signature

    cash_received = Column(Numeric(10, 2), nullable=True)
    change_returned = Column(Numeric(10, 2), nullable=True)
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    platform_fee_rate_snapshot = Column(Numeric(5, 2), nullable=True)
    platform_fee_amount = Column(Numeric(10, 2), nullable=True)
    gateway_fee_amount = Column(Numeric(10, 2), nullable=True)
    gateway_fee_tax_amount = Column(Numeric(10, 2), nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class RazorpayWebhookEvent(Base):
    """
    Raw Razorpay webhook delivery log and idempotency anchor (rule 26;
    ID-056). Razorpay may redeliver an event and events may arrive out of
    order, so every webhook is recorded here keyed by the provider's own
    event id *before* any business-logic processing, and processing itself
    is keyed off `provider_event_id` rather than any in-memory state.

    This is a platform-level raw event log, not a tenant-scoped table (no
    `business_id`) — the relevant business/booking/payment is resolved from
    the event payload during processing, against `Payment.razorpay_order_id`
    / `razorpay_payment_id`.
    """
    __tablename__ = "razorpay_webhook_events"

    id = Column(Integer, primary_key=True, index=True)

    provider_event_id = Column(String, nullable=False, unique=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    payload = Column(JSONVariant, nullable=False)

    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    # Received / Processed / Failed
    processing_status = Column(String, nullable=False, default="Received", index=True)


class Refund(Base):
    """
    Authoritative refund-processing record (rule 16/26; ID-053/ID-056).
    `Payment.status` is never mutated to represent a refund — `Refund` is
    the single source of truth for money returned, and `Payment` remains an
    immutable historical record of the original collection.

    `status`: Initiated -> Completed / Failed. A `Failed` refund is not
    retried in place; a new `Refund` row is created instead (idempotent via
    `razorpay_refund_id` for gateway refunds), preserving the failed
    attempt as history rather than overwriting it.

    `refund_method` (Gateway/Manual) follows ID-053: a refund against an
    online Razorpay payment is Gateway and carries `razorpay_refund_id`; a
    refund against cash/manual/direct-external payment is Manual, performed
    and verified by staff, and must never be marked Gateway-refunded.
    `calculated_amount` vs `overridden_amount` vs `final_amount`, plus
    `reason`/`actor_id`/`role_snapshot`, preserve the refund-override audit
    trail required by rule 16 without silently replacing the
    system-calculated figure. `platform_fee_reversal_amount` is the ID-051
    proportional platform-fee reversal for this refund.

    `booking_id` is nullable (Phase 5-7 addition): the ID-056
    payment-succeeds-after-hold-expiry exceptional path captures money
    against a `BookingHold` that never became a `Booking` (the slot was
    lost in the interim) — the automatic refund issued for that captured
    payment has no Booking to reference. Every other refund path (Phase 8+
    cancellation/reschedule refunds) always has a real booking_id.
    """
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False, index=True)
    # ondelete="CASCADE": dependent record of one Booking, matching BookingHistory.booking_id.
    # nullable: see docstring (ID-056 lost-hold refund has no Booking).
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)

    calculated_amount = Column(Numeric(10, 2), nullable=False)
    overridden_amount = Column(Numeric(10, 2), nullable=True)
    final_amount = Column(Numeric(10, 2), nullable=False)

    reason = Column(Text, nullable=True)  # application requires this when overridden_amount is set (rule 16)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_snapshot = Column(String, nullable=False)

    # Gateway / Manual (ID-053)
    refund_method = Column(String, nullable=False, index=True)
    razorpay_refund_id = Column(String, nullable=True, index=True)

    # Initiated / Completed / Failed
    status = Column(String, nullable=False, default="Initiated", index=True)

    platform_fee_reversal_amount = Column(Numeric(10, 2), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)


class Coupon(Base):
    """
    Coupon/promo-code configuration (rule 10). `branch_id` NULL means a
    business-wide coupon (created by the Business Owner, usable across all
    of the business's branches); a non-NULL `branch_id` is a branch-specific
    coupon requiring Business Owner approval (`approval_status`) before it
    can be used for that branch.

    An empty `coupon_services` set (see below) means the coupon applies to
    all services, mirroring the same "empty selection = no restriction"
    convention rule 10 itself specifies. `applicable_weekdays` follows the
    same convention: NULL/empty means no weekday restriction. `max_discount`
    NULL means no cap; `total_usage_limit` NULL means unlimited.

    Redemption/reservation concurrency lives in `CouponRedemption` and
    `BookingHold.price_snapshot` (see those docstrings), not here — this
    table only holds configuration, matching the codebase's established
    current-value-vs-usage-record split.
    """
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)

    # ondelete="CASCADE" on both: Coupon is a configuration entity, matching
    # the existing ServiceTemplate/BranchService business_id/branch_id
    # convention, not the no-cascade posture used for transactional/ledger
    # records like Booking/Payment/Refund.
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=True, index=True)  # NULL = business-wide

    code = Column(String, nullable=False, index=True)

    # Fixed / Percentage
    discount_type = Column(String, nullable=False)
    discount_value = Column(Numeric(10, 2), nullable=False)

    min_booking_amount = Column(Numeric(10, 2), nullable=False, default=0)
    max_discount = Column(Numeric(10, 2), nullable=True)  # NULL = no cap

    valid_from = Column(Date, nullable=False)
    valid_until = Column(Date, nullable=False)
    applicable_weekdays = Column(JSONVariant, nullable=True)  # NULL/empty = all weekdays; [0=Mon..6=Sun]

    total_usage_limit = Column(Integer, nullable=True)  # NULL = unlimited
    per_customer_usage_limit = Column(Integer, nullable=False, default=1)

    # Active / Inactive
    status = Column(String, nullable=False, default="Active", index=True)

    # NULL for business-wide (approval not applicable); Pending / Approved for branch-specific
    approval_status = Column(String, nullable=True, index=True)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("business_id", "code", name="uq_coupons_business_code"),
    )


class CouponService(Base):
    """
    Coupon <-> BranchService applicability (M2M). No row for a coupon means
    it applies to all services (rule 10), consistent with `Coupon`'s
    docstring.
    """
    __tablename__ = "coupon_services"

    id = Column(Integer, primary_key=True, index=True)

    # ondelete="CASCADE" on both, matching the existing
    # ServiceTemplateResourceCategory/BranchServiceResourceCategory M2M precedent.
    coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_service_id = Column(
        Integer, ForeignKey("branch_services.id", ondelete="CASCADE"), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("coupon_id", "branch_service_id", name="uq_coupon_services_coupon_service"),
    )


class CouponRedemption(Base):
    """
    Permanent record that a coupon was used on a booking (rule 10; ID-056).
    A row here is written only at checkout finalization (payment captured,
    or — for a 100%-off ₹0 booking — at booking confirmation itself, since
    there is no payment step to gate it), never at hold creation.

    Before finalization, an *Active* `BookingHold` whose `price_snapshot`
    references this coupon functions as a soft reservation of one unit of
    capacity (counted alongside completed redemptions when checking
    `total_usage_limit`/`per_customer_usage_limit` under a `SELECT ... FOR
    UPDATE` lock on the `Coupon` row). If the hold expires or is cancelled
    before finalization, no `CouponRedemption` row is ever created and the
    reserved capacity is simply no longer counted — there is no separate
    "release" action.

    `UniqueConstraint(coupon_id, booking_id)`: a booking redeems a given
    coupon at most once.
    """
    __tablename__ = "coupon_redemptions"

    id = Column(Integer, primary_key=True, index=True)

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False, index=True)
    # ondelete="CASCADE": dependent record of one Booking, matching BookingHistory.booking_id.
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("business_customers.id"), nullable=False, index=True)

    discount_applied_amount = Column(Numeric(10, 2), nullable=False)
    redeemed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("coupon_id", "booking_id", name="uq_coupon_redemptions_coupon_booking"),
        # Serves the ID-056/rule-10 per-customer usage-limit check
        # (count completed redemptions for this coupon+customer, under the
        # same Coupon-row lock used for the total-limit check).
        Index("ix_coupon_redemptions_coupon_customer", "coupon_id", "customer_id"),
    )


class BookingPriceAdjustment(Base):
    """
    Immutable price-adjustment history for a booking (rule 9/14), separate
    from `BookingHistory` (which tracks schedule/resource changes, not
    price). Covers manual base-price and final-price overrides (rule 9) and
    automatic reschedule price-difference collection/refund (rule 14).

    `reason` is nullable at the column level because not every
    `adjustment_type` requires one (a `ReschedulePriceDiff` is a system
    computation, not a manual override); the application enforces `reason`
    as mandatory for `BaseOverride`/`FinalOverride` per rule 9's "Both
    overrides ... require a reason." `previous_value`/`new_value` preserve
    the calculated/original and overridden amounts together, per rule 9's
    "Do not simply overwrite historical price information."
    """
    __tablename__ = "booking_price_adjustments"

    id = Column(Integer, primary_key=True, index=True)

    # ondelete="CASCADE": dependent record of one Booking, matching BookingHistory.booking_id.
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)

    # BaseOverride / FinalOverride / ReschedulePriceDiff
    adjustment_type = Column(String, nullable=False, index=True)

    previous_value = Column(Numeric(10, 2), nullable=True)
    new_value = Column(Numeric(10, 2), nullable=False)

    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_snapshot = Column(String, nullable=False)
    reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PlatformFeeSetting(Base):
    """
    Current effective platform online-transaction-fee percentage (ID-051).
    `business_id` NULL is the single platform-default row; a non-NULL
    `business_id` is that business's override. Effective rate = the
    business's override row if one exists, otherwise the NULL/default row
    (inheritance, not copy-on-write — a later default change affects every
    business without an override, per ID-051/rule 17).

    This table intentionally holds only the *current* value — every change
    (setting, changing, or removing an override) is additionally written to
    the existing generic `AuditLog` (entity_type="PlatformFeeSetting",
    previous_value, new_value, reason, performed_by), the same
    current-state-vs-history split already used elsewhere in this codebase
    (e.g. Branch/Business approval state vs. its audit trail), rather than
    duplicating `reason`/`previous_value`/actor columns on this table too.
    A reason is required by the application whenever `business_id` is not
    NULL (ID-051); the platform-default row's own changes are still
    audited, just without a mandatory reason.

    Once a booking's first financial transaction occurs, the then-effective
    rate is copied onto `BookingFinancial.platform_fee_rate_snapshot`
    (ID-051) and this table is never consulted again for that booking.

    Singleton/uniqueness is enforced at the database level, not only in
    application logic: the plain unique constraint on `business_id` caps
    each business at one override row (Postgres/SQLite unique constraints
    treat each non-NULL value as unique, which is exactly "at most one row
    per business"). The platform-default row needs a second, differently
    shaped index: a unique index *on the nullable column itself*, even
    filtered `WHERE business_id IS NULL`, does NOT work — verified
    empirically against real PostgreSQL during Phase 1B (two `business_id
    IS NULL` rows inserted successfully). Standard SQL unique-index
    semantics treat every NULL as distinct from every other NULL
    regardless of a partial predicate restricting which rows participate,
    so a unique index on `business_id` never flags two NULLs as
    duplicates. The fix is the standard Postgres idiom for "at most one row
    matching a predicate": a unique index on a *constant expression*
    (`1`, never NULL) filtered by the same predicate — every qualifying
    row indexes to the same non-NULL key, so a second one is a genuine
    duplicate. This still needs no Postgres-only DDL: it uses the same
    dialect-conditional `Index(postgresql_where=..., sqlite_where=...)`
    trick ID-043 established, so it lives in `Base.metadata` and is created
    by both `create_all()` (tests) and the Phase 1B migration.
    """
    __tablename__ = "platform_fee_settings"

    id = Column(Integer, primary_key=True, index=True)

    # ondelete="CASCADE": configuration entity, matching the
    # ServiceTemplate/BranchService/Coupon business_id convention. NULL
    # (the platform-default row) is never subject to this FK at all.
    business_id = Column(
        Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True, unique=True, index=True
    )
    fee_percentage = Column(Numeric(5, 2), nullable=False)

    updated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        # Caps the business_id IS NULL row at exactly one — see docstring.
        # Indexes the constant `1`, not `business_id`, because a unique
        # index on the nullable column itself would never treat two NULLs
        # as a duplicate (verified empirically; see docstring).
        Index(
            "uq_platform_fee_settings_default_row",
            text("(1)"),
            unique=True,
            postgresql_where=text("business_id IS NULL"),
            sqlite_where=text("business_id IS NULL"),
        ),
    )


class Notification(Base):
    """
    Notification request/delivery tracking (TAS Part 3 §10 — specified in
    the frozen schema but never implemented through M7; built now per
    ID-050 since M8 needs an auditable record of, e.g., "balance reminder
    sent"). `business_id` is added beyond the literal TAS §10 column list,
    nullable, mirroring `AuditLog.business_id` (also TAS-specified nullable)
    for the same tenant-scoped-query reason ID-012/ID-024 already
    established for other entities.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)

    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=True, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    notification_type = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False, default="Email")

    # Pending / Sent / Failed
    status = Column(String, nullable=False, default="Pending", index=True)
    payload = Column(JSONVariant, nullable=True)

    related_entity_type = Column(String, nullable=True, index=True)
    related_entity_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at = Column(DateTime, nullable=True)


class EmailLog(Base):
    """
    Email delivery attempt log (TAS Part 3 §10, implemented now per
    ID-050 — see `Notification`).
    """
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, index=True)

    # ondelete="CASCADE": pure dependent child of Notification, matching
    # BookingHistory.booking_id / BusinessCustomer.platform_customer_id
    # (a record meaningless without its parent).
    notification_id = Column(Integer, ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False, index=True)

    smtp_provider = Column(String, nullable=True)
    delivery_status = Column(String, nullable=False, default="Attempted", index=True)
    provider_reference = Column(String, nullable=True)

    attempted_at = Column(DateTime, default=datetime.utcnow, nullable=False)