"""add booking engine

Revision ID: b7e3a1f9c4d2
Revises: 302fd62fdba4
Create Date: 2026-08-31 00:00:00.000000

Milestone 7 (Booking Engine & Customer Booking Experience) — TAS Part 3 §9;
PRD §16, §18-24.

This is an explicitly-authorized schema *replacement*, not a purely
additive change (IMPLEMENTATION_PLAN.md M7 scope bullet 1: "Replace/
generalize the legacy booking structure as required by V1"):

- Drops the pre-Milestone-7 flat `bookings` table (`date`, `time`,
  `user_id` only; global `unique_booking_slot`; no business/branch/
  service/resource linkage; no status; supported a hard-delete admin
  endpoint that directly contradicted BR-045 "Deletion is prohibited").
- Creates the new tenant-aware `bookings` table (TAS §9 columns plus
  `cancellation_reason` / `completed_at`, ID-036) with `business_id`,
  `branch_id`, `customer_id` (-> business_customers), `branch_service_id`
  (-> branch_services), `resource_id`, `booking_date`, `start_time`,
  `end_time`, `status`. Indexes on business_id/branch_id/booking_date/
  resource_id/status per TAS §9. `(resource_id, booking_date, start_time)`
  is kept unique as a defense-in-depth backstop, but only as a *partial*
  index excluding Cancelled rows — a cancelled booking releases the
  resource (PRD §20) and must not permanently block that exact slot from
  being rebooked; general overlap detection is enforced in application
  logic (ID-037).
- Creates `booking_history` (TAS §9 / PRD §22): immutable per-booking
  history, `previous_state`/`new_state` as structured JSONB (JSON on
  SQLite) snapshots.

No data migration: the legacy `bookings` table's rows (plain date/time
slots with no tenant/customer/service/resource linkage) cannot be mapped
into the new schema and are dropped along with the table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b7e3a1f9c4d2'
down_revision: Union[str, Sequence[str], None] = '302fd62fdba4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table("bookings")

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("business_customers.id"), nullable=False),
        sa.Column("branch_service_id", sa.Integer(), sa.ForeignKey("branch_services.id"), nullable=False),
        sa.Column("resource_id", sa.Integer(), sa.ForeignKey("resources.id"), nullable=False),
        sa.Column("booking_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="Confirmed"),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "uq_booking_resource_date_start_time",
        "bookings",
        ["resource_id", "booking_date", "start_time"],
        unique=True,
        postgresql_where=sa.text("status != 'Cancelled'"),
    )
    op.create_index(op.f("ix_bookings_business_id"), "bookings", ["business_id"])
    op.create_index(op.f("ix_bookings_branch_id"), "bookings", ["branch_id"])
    op.create_index(op.f("ix_bookings_customer_id"), "bookings", ["customer_id"])
    op.create_index(op.f("ix_bookings_branch_service_id"), "bookings", ["branch_service_id"])
    op.create_index(op.f("ix_bookings_resource_id"), "bookings", ["resource_id"])
    op.create_index(op.f("ix_bookings_booking_date"), "bookings", ["booking_date"])
    op.create_index(op.f("ix_bookings_status"), "bookings", ["status"])

    op.create_table(
        "booking_history",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column(
            "previous_state",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column(
            "new_state",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("performed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("performed_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_booking_history_booking_id"), "booking_history", ["booking_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("booking_history")
    op.drop_table("bookings")

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("time", sa.Time(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("date", "time", name="unique_booking_slot"),
    )
    op.create_index(op.f("ix_bookings_date"), "bookings", ["date"])
    op.create_index(op.f("ix_bookings_user_id"), "bookings", ["user_id"])
    op.create_index("idx_booking_user_date", "bookings", ["user_id", "date"])
