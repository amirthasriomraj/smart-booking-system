"""add booking holds and occupancy constraints

Revision ID: 59d14c6b7ce1
Revises: b7e3a1f9c4d2
Create Date: 2026-09-03 13:56:34.708170

Milestone 8 (Payments, Financial Policies & Promotions) — ID-046, ID-056.

Creates `booking_holds` (temporary, database-authoritative checkout/payment
holds — a separate entity from `Booking`, never a provisional `Confirmed`
booking; see `models.BookingHold`).

Also adds PostgreSQL-only GiST exclusion constraints on `booking_holds` and
the existing `bookings` table for true interval-overlap protection. These
are hand-written DDL, deliberately NOT represented in `Base.metadata`/the
SQLAlchemy models:

- `ExcludeConstraint` has no SQLite equivalent (unlike the
  dialect-conditional `postgresql_where`/`sqlite_where` trick ID-043 used
  for the existing plain partial index), so declaring it in ORM metadata
  would break `Base.metadata.create_all()` against the SQLite engine
  `tests/conftest.py` uses. They are therefore maintained by hand in this
  migration only and will never be detected by `alembic --autogenerate` or
  proven by the SQLite-based test suite — PostgreSQL integration
  verification (see the Phase 1B completion report) is required instead.

IMPORTANT — what these constraints do and do not do:

- They are defense-in-depth for raw interval overlap only, mirroring the
  role the existing `uq_booking_resource_date_start_time` partial index
  already plays for `bookings` (ID-043) but upgraded to true
  `[start_time, end_time)` overlap instead of exact-`start_time` equality
  (the plain partial index cannot catch e.g. 10:00-11:00 vs 10:15-11:15,
  which share no `start_time` but do overlap).
- They do NOT enforce `Resource.booking_buffer_minutes` padding — buffer
  semantics remain purely an application-level concern
  (`_overlaps_with_buffer` in `crud_booking.py`).
- They do NOT by themselves prevent a `Booking` from overlapping a
  `BookingHold` — a GiST exclusion constraint is scoped to one table, so a
  `bookings` overlap and a `booking_holds` overlap are each independently
  enforced, but nothing at the database level enforces overlap *between*
  the two tables.
- The transaction-scoped `pg_advisory_xact_lock(resource_id, date_key)`
  (application code, M8 checkout/booking-creation paths — not part of this
  migration) remains the single authoritative mechanism covering all four
  cases: Booking vs Booking, Hold vs Hold, Booking vs Hold, and buffer
  semantics. These constraints are a backstop that should never actually
  fire in the happy path, not the source of truth.
- The `bookings` predicate below (`status <> 'Cancelled'`) is copied
  verbatim from the existing `uq_booking_resource_date_start_time` index's
  `postgresql_where` clause — it does not change which Booking statuses
  occupy availability. The existing plain partial index is left in place
  (additive, redundant-but-harmless defense-in-depth layered under the
  stronger GiST constraint) rather than dropped, so the already-reviewed
  M7 `Booking` model/migration is not touched by this milestone.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '59d14c6b7ce1'
down_revision: Union[str, Sequence[str], None] = 'b7e3a1f9c4d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Required by both GiST exclusion constraints below (equality on an
    # integer column plus range overlap in the same index). Approved for
    # local development (M8 Phase 1B decision 2); availability/CREATE
    # EXTENSION privilege on future managed/RDS PostgreSQL is a deployment
    # prerequisite, not a local-implementation blocker.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "booking_holds",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("branch_service_id", sa.Integer(), sa.ForeignKey("branch_services.id"), nullable=False),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("business_customers.id"), nullable=False),
        sa.Column("booking_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("hold_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="Active"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "price_snapshot",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_booking_holds_business_id"), "booking_holds", ["business_id"])
    op.create_index(op.f("ix_booking_holds_branch_id"), "booking_holds", ["branch_id"])
    op.create_index(op.f("ix_booking_holds_branch_service_id"), "booking_holds", ["branch_service_id"])
    op.create_index(op.f("ix_booking_holds_resource_id"), "booking_holds", ["resource_id"])
    op.create_index(op.f("ix_booking_holds_customer_id"), "booking_holds", ["customer_id"])
    op.create_index(op.f("ix_booking_holds_booking_date"), "booking_holds", ["booking_date"])
    op.create_index(op.f("ix_booking_holds_hold_type"), "booking_holds", ["hold_type"])
    op.create_index(op.f("ix_booking_holds_status"), "booking_holds", ["status"])
    op.create_index(op.f("ix_booking_holds_expires_at"), "booking_holds", ["expires_at"])
    op.create_index(
        "ix_booking_holds_resource_date_status",
        "booking_holds",
        ["resource_id", "booking_date", "status"],
    )

    # True interval-overlap, defense-in-depth only (see module docstring).
    # Only an Active hold occupies the resource interval.
    op.execute(
        """
        ALTER TABLE booking_holds
        ADD CONSTRAINT excl_booking_holds_no_overlap
        EXCLUDE USING gist (
            resource_id WITH =,
            tsrange(
                (booking_date + start_time)::timestamp,
                (booking_date + end_time)::timestamp
            ) WITH &&
        ) WHERE (status = 'Active')
        """
    )

    # Same true-overlap upgrade for the existing `bookings` table, using the
    # identical occupancy predicate as the existing partial unique index
    # (status <> 'Cancelled' — Confirmed and Completed both occupy the
    # slot, only Cancelled releases it) so this does not redefine M7
    # availability semantics.
    op.execute(
        """
        ALTER TABLE bookings
        ADD CONSTRAINT excl_bookings_no_overlap
        EXCLUDE USING gist (
            resource_id WITH =,
            tsrange(
                (booking_date + start_time)::timestamp,
                (booking_date + end_time)::timestamp
            ) WITH &&
        ) WHERE (status <> 'Cancelled')
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS excl_bookings_no_overlap")
    op.execute("ALTER TABLE booking_holds DROP CONSTRAINT IF EXISTS excl_booking_holds_no_overlap")
    op.drop_table("booking_holds")
    # Deliberately not dropping the btree_gist extension: it may be relied
    # on by other objects, and PostgreSQL extensions are conventionally left
    # installed once added rather than removed on downgrade.
