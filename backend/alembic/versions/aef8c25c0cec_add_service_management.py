"""add service management

Revision ID: aef8c25c0cec
Revises: 9d3465940d54
Create Date: 2026-08-27 00:00:00.000000

Adds the Milestone 5 (Service Management) schema (TAS Part 3 §8;
PRD §15.1-15.6):

- service_templates: business-level master service definition (PRD §15.1).
  Carries an explicit business_id (ID-024 — the TAS §8 Service Templates
  column list omits it, but the TAS's "Entities requiring business_id" list
  names both Service Template and Branch Service). Also carries
  default_buffer_minutes / default_working_rules, V1-mandatory attributes
  (PRD §15.1) the TAS schema has no columns for (ID-025 — storage only,
  default_working_rules is opaque JSON with no defined structure).
- service_template_resource_categories: default Resource Category
  assignment for a Service Template (PRD §15.1/§15.6).
- branch_services: branch-specific implementation of a Service Template
  (PRD §15.2-15.4). Always references a template (ID-018); carries a
  denormalized business_id (ID-024); status is a 5-value lifecycle with no
  separate "Active" state (ID-020).
- branch_service_resource_categories: live/effective, branch-overridable
  Resource Category assignment for a Branch Service (PRD §15.6).
- service_approvals: tracks Branch Service override approvals (PRD §15.4,
  §25.5). previous_configuration / proposed_configuration are structured
  JSON snapshots not in the TAS §8 column list (ID-021), using JSONB on
  PostgreSQL with a plain JSON fallback for the SQLite test database.

Purely additive: no existing column is altered, no data is migrated.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'aef8c25c0cec'
down_revision: Union[str, Sequence[str], None] = '9d3465940d54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "service_templates",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("default_duration", sa.Integer(), nullable=False),
        sa.Column("default_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("default_buffer_minutes", sa.Integer(), nullable=True),
        sa.Column("default_working_rules", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="Active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        op.f("ix_service_templates_business_id"), "service_templates", ["business_id"], unique=False
    )
    op.create_index(
        op.f("ix_service_templates_status"), "service_templates", ["status"], unique=False
    )

    op.create_table(
        "service_template_resource_categories",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "service_template_id", sa.Integer(),
            sa.ForeignKey("service_templates.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("resource_category_id", sa.Integer(), sa.ForeignKey("resource_categories.id"), nullable=False),
        sa.UniqueConstraint(
            "service_template_id", "resource_category_id",
            name="uq_service_template_resource_category",
        ),
    )
    op.create_index(
        op.f("ix_service_template_resource_categories_service_template_id"),
        "service_template_resource_categories", ["service_template_id"], unique=False,
    )
    op.create_index(
        op.f("ix_service_template_resource_categories_resource_category_id"),
        "service_template_resource_categories", ["resource_category_id"], unique=False,
    )

    op.create_table(
        "branch_services",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_template_id", sa.Integer(), sa.ForeignKey("service_templates.id"), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="Approved"),
        sa.Column("pending_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("branch_id", "service_template_id", name="uq_branch_service_branch_template"),
    )
    op.create_index(op.f("ix_branch_services_branch_id"), "branch_services", ["branch_id"], unique=False)
    op.create_index(op.f("ix_branch_services_business_id"), "branch_services", ["business_id"], unique=False)
    op.create_index(
        op.f("ix_branch_services_service_template_id"), "branch_services", ["service_template_id"], unique=False
    )
    op.create_index(op.f("ix_branch_services_status"), "branch_services", ["status"], unique=False)

    op.create_table(
        "branch_service_resource_categories",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "branch_service_id", sa.Integer(),
            sa.ForeignKey("branch_services.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("resource_category_id", sa.Integer(), sa.ForeignKey("resource_categories.id"), nullable=False),
        sa.UniqueConstraint(
            "branch_service_id", "resource_category_id",
            name="uq_branch_service_resource_category",
        ),
    )
    op.create_index(
        op.f("ix_branch_service_resource_categories_branch_service_id"),
        "branch_service_resource_categories", ["branch_service_id"], unique=False,
    )
    op.create_index(
        op.f("ix_branch_service_resource_categories_resource_category_id"),
        "branch_service_resource_categories", ["resource_category_id"], unique=False,
    )

    op.create_table(
        "service_approvals",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "branch_service_id", sa.Integer(),
            sa.ForeignKey("branch_services.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decision", sa.String(), nullable=False, server_default="Pending"),
        sa.Column("previous_configuration", postgresql.JSONB(), nullable=False),
        sa.Column("proposed_configuration", postgresql.JSONB(), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        op.f("ix_service_approvals_branch_service_id"), "service_approvals", ["branch_service_id"], unique=False
    )
    op.create_index(op.f("ix_service_approvals_decision"), "service_approvals", ["decision"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_service_approvals_decision"), table_name="service_approvals")
    op.drop_index(op.f("ix_service_approvals_branch_service_id"), table_name="service_approvals")
    op.drop_table("service_approvals")

    op.drop_index(
        op.f("ix_branch_service_resource_categories_resource_category_id"),
        table_name="branch_service_resource_categories",
    )
    op.drop_index(
        op.f("ix_branch_service_resource_categories_branch_service_id"),
        table_name="branch_service_resource_categories",
    )
    op.drop_table("branch_service_resource_categories")

    op.drop_index(op.f("ix_branch_services_status"), table_name="branch_services")
    op.drop_index(op.f("ix_branch_services_service_template_id"), table_name="branch_services")
    op.drop_index(op.f("ix_branch_services_business_id"), table_name="branch_services")
    op.drop_index(op.f("ix_branch_services_branch_id"), table_name="branch_services")
    op.drop_table("branch_services")

    op.drop_index(
        op.f("ix_service_template_resource_categories_resource_category_id"),
        table_name="service_template_resource_categories",
    )
    op.drop_index(
        op.f("ix_service_template_resource_categories_service_template_id"),
        table_name="service_template_resource_categories",
    )
    op.drop_table("service_template_resource_categories")

    op.drop_index(op.f("ix_service_templates_status"), table_name="service_templates")
    op.drop_index(op.f("ix_service_templates_business_id"), table_name="service_templates")
    op.drop_table("service_templates")
