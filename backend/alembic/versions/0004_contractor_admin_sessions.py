"""contractor admin sessions (FR-001)

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ADMIN_FLOW_TYPE = ("manage_rates", "onboard")
ADMIN_SESSION_STATE = (
    "awaiting_business_name",
    "awaiting_city",
    "awaiting_slug",
    "awaiting_work_type",
    "awaiting_content",
    "reviewing",
    "creating_account",
    "completed",
    "cancelled",
)


def upgrade() -> None:
    admin_flow_type = postgresql.ENUM(*ADMIN_FLOW_TYPE, name="admin_flow_type", create_type=False)
    admin_session_state = postgresql.ENUM(*ADMIN_SESSION_STATE, name="admin_session_state", create_type=False)
    admin_flow_type.create(op.get_bind(), checkfirst=True)
    admin_session_state.create(op.get_bind(), checkfirst=True)

    work_type = postgresql.ENUM("painting", "false_ceiling", name="work_type", create_type=False)

    op.create_table(
        "contractor_admin_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "contractor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contractors.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("admin_phone", sa.String(length=32), nullable=False),
        sa.Column(
            "flow_type",
            admin_flow_type,
            nullable=False,
        ),
        sa.Column(
            "state",
            admin_session_state,
            nullable=False,
        ),
        sa.Column("work_type", work_type, nullable=True),
        sa.Column("draft_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("draft_profile", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "parse_notes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "validation_errors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_contractor_admin_sessions_admin_phone",
        "contractor_admin_sessions",
        ["admin_phone"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_contractor_admin_sessions_admin_phone",
        table_name="contractor_admin_sessions",
    )
    op.drop_table("contractor_admin_sessions")
    op.execute("DROP TYPE IF EXISTS admin_session_state")
    op.execute("DROP TYPE IF EXISTS admin_flow_type")
