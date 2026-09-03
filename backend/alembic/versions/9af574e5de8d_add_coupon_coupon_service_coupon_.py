"""add coupon coupon service coupon redemption

Revision ID: 9af574e5de8d
Revises: d9492e8901e0
Create Date: 2026-09-03 13:56:47.000000

Milestone 8 — rule 10, ID-056.

Creates `coupons` (configuration), `coupon_services` (M2M applicability —
empty means all services), and `coupon_redemptions` (permanent record that
a coupon was used on a booking; written only at checkout finalization, not
at hold creation — see `models.Coupon`/`CouponService`/`CouponRedemption`).
Coupon capacity *reservation* during an active checkout hold is represented
by `booking_holds.price_snapshot`, not a separate table (see
`models.BookingHold`).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9af574e5de8d'
down_revision: Union[str, Sequence[str], None] = 'd9492e8901e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "coupons",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("discount_type", sa.String(), nullable=False),
        sa.Column("discount_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("min_booking_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("max_discount", sa.Numeric(10, 2), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column(
            "applicable_weekdays",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
        sa.Column("total_usage_limit", sa.Integer(), nullable=True),
        sa.Column("per_customer_usage_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(), nullable=False, server_default="Active"),
        sa.Column("approval_status", sa.String(), nullable=True),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("business_id", "code", name="uq_coupons_business_code"),
    )
    op.create_index(op.f("ix_coupons_business_id"), "coupons", ["business_id"])
    op.create_index(op.f("ix_coupons_branch_id"), "coupons", ["branch_id"])
    op.create_index(op.f("ix_coupons_code"), "coupons", ["code"])
    op.create_index(op.f("ix_coupons_status"), "coupons", ["status"])
    op.create_index(op.f("ix_coupons_approval_status"), "coupons", ["approval_status"])

    op.create_table(
        "coupon_services",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("coupon_id", sa.Integer(), sa.ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "branch_service_id",
            sa.Integer(),
            sa.ForeignKey("branch_services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("coupon_id", "branch_service_id", name="uq_coupon_services_coupon_service"),
    )
    op.create_index(op.f("ix_coupon_services_coupon_id"), "coupon_services", ["coupon_id"])
    op.create_index(op.f("ix_coupon_services_branch_service_id"), "coupon_services", ["branch_service_id"])

    op.create_table(
        "coupon_redemptions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("coupon_id", sa.Integer(), sa.ForeignKey("coupons.id"), nullable=False),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("business_customers.id"), nullable=False),
        sa.Column("discount_applied_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("coupon_id", "booking_id", name="uq_coupon_redemptions_coupon_booking"),
    )
    op.create_index(op.f("ix_coupon_redemptions_business_id"), "coupon_redemptions", ["business_id"])
    op.create_index(op.f("ix_coupon_redemptions_coupon_id"), "coupon_redemptions", ["coupon_id"])
    op.create_index(op.f("ix_coupon_redemptions_booking_id"), "coupon_redemptions", ["booking_id"])
    op.create_index(op.f("ix_coupon_redemptions_customer_id"), "coupon_redemptions", ["customer_id"])
    op.create_index(
        "ix_coupon_redemptions_coupon_customer", "coupon_redemptions", ["coupon_id", "customer_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("coupon_redemptions")
    op.drop_table("coupon_services")
    op.drop_table("coupons")
