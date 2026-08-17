"""add tenant foundation rbac business audit

Revision ID: 915a434bff35
Revises: 9bc15c779634
Create Date: 2026-08-16 23:15:16.041652

Adds the Milestone 1 tenant/identity/audit foundation (TAS Part 3 §2, §3,
§5, §10; PRD §12, §25.3):

- roles / user_roles: frozen platform-scoped RBAC model
- countries / business_categories: registration reference data
- businesses: tenant registration + Platform Admin approval lifecycle
- business_members: business-scoped RBAC (Business Owner, ...)
- audit_logs: append-only audit trail

Purely additive: no existing table is modified.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '915a434bff35'
down_revision: Union[str, Sequence[str], None] = '9bc15c779634'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLES = [
    {"code": "PLATFORM_ADMIN", "name": "Platform Administrator", "description": "Manages the platform itself; approves businesses and branches."},
    {"code": "BUSINESS_OWNER", "name": "Business Owner", "description": "Primary administrator of a tenant business."},
    {"code": "BRANCH_MANAGER", "name": "Branch Manager", "description": "Administers a single approved branch."},
    {"code": "HR_USER", "name": "Human Resource User", "description": "Manages employee-related operations for the business."},
    {"code": "RESOURCE_USER", "name": "Resource User", "description": "A resource (e.g. doctor, trainer) with login access."},
    {"code": "CUSTOMER", "name": "Customer", "description": "Consumes services offered by a business."},
]

# PRD §12 Step 1 example business category list.
BUSINESS_CATEGORIES = [
    "Clinic",
    "Hospital",
    "Salon",
    "Spa",
    "Sports Centre",
    "Fitness Centre",
    "Coaching Institute",
    "Photography Studio",
    "Equipment Rental",
    "Professional Services",
    "Other",
]

# Minimal seed set (PRD §56: V1 focuses primarily on the Indian market).
COUNTRIES = [
    {"iso_code": "IN", "name": "India", "currency_code": "INR", "timezone": "Asia/Kolkata"},
    {"iso_code": "US", "name": "United States", "currency_code": "USD", "timezone": "America/New_York"},
    {"iso_code": "GB", "name": "United Kingdom", "currency_code": "GBP", "timezone": "Europe/London"},
]


def upgrade() -> None:
    """Upgrade schema."""

    roles_table = op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_index(op.f("ix_roles_code"), "roles", ["code"], unique=True)

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_user_roles_user_id"), "user_roles", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_roles_role_id"), "user_roles", ["role_id"], unique=False)

    countries_table = op.create_table(
        "countries",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("iso_code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("currency_code", sa.String(), nullable=True),
        sa.Column("timezone", sa.String(), nullable=True),
        sa.UniqueConstraint("iso_code", name="uq_countries_iso_code"),
    )
    op.create_index(op.f("ix_countries_iso_code"), "countries", ["iso_code"], unique=True)

    business_categories_table = op.create_table(
        "business_categories",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("name", name="uq_business_categories_name"),
    )

    op.create_table(
        "businesses",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_name", sa.String(), nullable=False),
        sa.Column("business_category_id", sa.Integer(), sa.ForeignKey("business_categories.id"), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("country_id", sa.Integer(), sa.ForeignKey("countries.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="Pending"),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("owner_user_id", name="uq_businesses_owner_user_id"),
    )
    op.create_index(op.f("ix_businesses_business_name"), "businesses", ["business_name"], unique=False)
    op.create_index(op.f("ix_businesses_status"), "businesses", ["status"], unique=False)

    op.create_table(
        "business_members",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="Active"),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("left_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("business_id", "user_id", name="uq_business_member_business_user"),
    )
    op.create_index(op.f("ix_business_members_business_id"), "business_members", ["business_id"], unique=False)
    op.create_index(op.f("ix_business_members_user_id"), "business_members", ["user_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id"), nullable=True),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("previous_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("performed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(op.f("ix_audit_logs_business_id"), "audit_logs", ["business_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_entity_type"), "audit_logs", ["entity_type"], unique=False)
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)

    # --- Seed data ---
    op.bulk_insert(
        roles_table,
        [{"code": r["code"], "name": r["name"], "description": r["description"]} for r in ROLES],
    )
    op.bulk_insert(
        countries_table,
        COUNTRIES,
    )
    op.bulk_insert(
        business_categories_table,
        [{"name": name, "description": None, "is_active": True} for name in BUSINESS_CATEGORIES],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("audit_logs")
    op.drop_table("business_members")
    op.drop_table("businesses")
    op.drop_table("business_categories")
    op.drop_table("countries")
    op.drop_table("user_roles")
    op.drop_table("roles")
