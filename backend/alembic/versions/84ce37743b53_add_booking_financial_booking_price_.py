"""add booking financial booking price adjustment platform fee setting notification email log

Revision ID: 84ce37743b53
Revises: 9af574e5de8d
Create Date: 2026-09-03 13:56:51.000000

Milestone 8 — ID-045, ID-048, ID-050, ID-051, rule 9/14/17/27.

Creates:
- `booking_financials`: per-booking financial state, deliberately separate
  from `Booking.status` (ID-045).
- `booking_price_adjustments`: immutable price-override/reschedule-diff
  history (rule 9/14).
- `platform_fee_settings`: current effective platform fee percentage, with
  a business_id unique constraint (at most one override row per business)
  plus a partial unique index enforcing at most one platform-default row
  (business_id IS NULL) — the database-level singleton guarantee requested
  for M8 Phase 1B decision 3. Unlike the GiST exclusion constraints in the
  first M8 migration, this partial index needs no hand-written DDL: it is
  declared in `models.PlatformFeeSetting.__table_args__` using the same
  dialect-conditional `Index(postgresql_where=..., sqlite_where=...)`
  pattern ID-043 already established, so it is created here via the
  ordinary `postgresql_where` form (this file only ever runs against
  PostgreSQL).
- `notifications` / `email_logs`: TAS Part 3 §10 tables, specified in the
  frozen schema but never implemented through M7, built now per ID-050.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '84ce37743b53'
down_revision: Union[str, Sequence[str], None] = '9af574e5de8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "booking_financials",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "booking_id",
            sa.Integer(),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("amount_refunded", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("deposit_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deposit_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("balance_due", sa.Numeric(10, 2), nullable=True),
        sa.Column("balance_due_at", sa.DateTime(), nullable=True),
        sa.Column("balance_reminder_sent_at", sa.DateTime(), nullable=True),
        sa.Column("financial_status", sa.String(), nullable=False),
        sa.Column("platform_fee_rate_snapshot", sa.Numeric(5, 2), nullable=True),
        sa.Column("coupon_id", sa.Integer(), sa.ForeignKey("coupons.id"), nullable=True),
        sa.Column("base_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("base_price_override", sa.Numeric(10, 2), nullable=True),
        sa.Column("final_price_override", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_booking_financials_booking_id"), "booking_financials", ["booking_id"])
    op.create_index(op.f("ix_booking_financials_business_id"), "booking_financials", ["business_id"])
    op.create_index(op.f("ix_booking_financials_branch_id"), "booking_financials", ["branch_id"])
    op.create_index(op.f("ix_booking_financials_balance_due_at"), "booking_financials", ["balance_due_at"])
    op.create_index(op.f("ix_booking_financials_financial_status"), "booking_financials", ["financial_status"])
    op.create_index(op.f("ix_booking_financials_coupon_id"), "booking_financials", ["coupon_id"])
    op.create_index(
        "ix_booking_financials_status_balance_due_at",
        "booking_financials",
        ["financial_status", "balance_due_at"],
    )

    op.create_table(
        "booking_price_adjustments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("adjustment_type", sa.String(), nullable=False),
        sa.Column("previous_value", sa.Numeric(10, 2), nullable=True),
        sa.Column("new_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role_snapshot", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_booking_price_adjustments_booking_id"), "booking_price_adjustments", ["booking_id"])
    op.create_index(
        op.f("ix_booking_price_adjustments_adjustment_type"), "booking_price_adjustments", ["adjustment_type"]
    )

    op.create_table(
        "platform_fee_settings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True),
        sa.Column("fee_percentage", sa.Numeric(5, 2), nullable=False),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("business_id", name="uq_platform_fee_settings_business_id"),
    )
    op.create_index(op.f("ix_platform_fee_settings_business_id"), "platform_fee_settings", ["business_id"])
    # Database-level singleton guarantee for the platform-default row (M8
    # Phase 1B decision 3): the UniqueConstraint above already caps each
    # non-NULL business_id at one row. For the business_id IS NULL row, a
    # unique index on `business_id` itself does NOT work — verified
    # empirically against PostgreSQL: standard SQL unique-index semantics
    # treat every NULL as distinct from every other NULL even under a
    # partial predicate, so two `business_id IS NULL` rows would both be
    # accepted. The fix is a unique index on the constant expression `1`
    # (never NULL), filtered by the same predicate, so every qualifying row
    # indexes to the same key and a second one is a genuine duplicate.
    op.create_index(
        "uq_platform_fee_settings_default_row",
        "platform_fee_settings",
        [sa.text("(1)")],
        unique=True,
        postgresql_where=sa.text("business_id IS NULL"),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id"), nullable=True),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notification_type", sa.String(), nullable=False),
        sa.Column("channel", sa.String(), nullable=False, server_default="Email"),
        sa.Column("status", sa.String(), nullable=False, server_default="Pending"),
        sa.Column(
            "payload",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("related_entity_type", sa.String(), nullable=True),
        sa.Column("related_entity_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_notifications_business_id"), "notifications", ["business_id"])
    op.create_index(op.f("ix_notifications_recipient_user_id"), "notifications", ["recipient_user_id"])
    op.create_index(op.f("ix_notifications_notification_type"), "notifications", ["notification_type"])
    op.create_index(op.f("ix_notifications_status"), "notifications", ["status"])
    op.create_index(op.f("ix_notifications_related_entity_type"), "notifications", ["related_entity_type"])

    op.create_table(
        "email_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "notification_id", sa.Integer(), sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("smtp_provider", sa.String(), nullable=True),
        sa.Column("delivery_status", sa.String(), nullable=False, server_default="Attempted"),
        sa.Column("provider_reference", sa.String(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_email_logs_notification_id"), "email_logs", ["notification_id"])
    op.create_index(op.f("ix_email_logs_delivery_status"), "email_logs", ["delivery_status"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("email_logs")
    op.drop_table("notifications")
    op.drop_table("platform_fee_settings")
    op.drop_table("booking_price_adjustments")
    op.drop_table("booking_financials")
