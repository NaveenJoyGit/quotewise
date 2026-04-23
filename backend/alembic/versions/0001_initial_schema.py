"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


WORK_TYPE = ("painting", "false_ceiling")
APPROVAL_MODE = ("always_approve", "auto_approve_above_confidence")
SESSION_STATE = (
    "greeting",
    "identifying_scope",
    "collecting_inputs",
    "clarifying",
    "ready_to_quote",
    "awaiting_approval",
    "quote_delivered",
    "closed",
)
MESSAGE_DIRECTION = ("inbound", "outbound")
MESSAGE_TYPE = ("text", "voice", "image", "document")
QUOTE_STATUS = (
    "draft",
    "pending_approval",
    "approved",
    "rejected",
    "sent",
    "expired",
)


def upgrade() -> None:
    work_type = postgresql.ENUM(*WORK_TYPE, name="work_type", create_type=False)
    approval_mode = postgresql.ENUM(*APPROVAL_MODE, name="approval_mode", create_type=False)
    session_state = postgresql.ENUM(*SESSION_STATE, name="session_state", create_type=False)
    message_direction = postgresql.ENUM(
        *MESSAGE_DIRECTION, name="message_direction", create_type=False
    )
    message_type = postgresql.ENUM(*MESSAGE_TYPE, name="message_type", create_type=False)
    quote_status = postgresql.ENUM(*QUOTE_STATUS, name="quote_status", create_type=False)

    for e in (
        work_type,
        approval_mode,
        session_state,
        message_direction,
        message_type,
        quote_status,
    ):
        e.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "contractors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("business_name", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("whatsapp_link_slug", sa.String(length=64), nullable=False),
        sa.Column("logo_url", sa.String(length=1024), nullable=True),
        sa.Column("gst_number", sa.String(length=32), nullable=True),
        sa.Column("approval_mode", approval_mode, nullable=False),
        sa.Column("confidence_threshold", sa.Float(), nullable=False),
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
        sa.UniqueConstraint("phone", name="uq_contractors_phone"),
        sa.UniqueConstraint("whatsapp_link_slug", name="uq_contractors_whatsapp_link_slug"),
    )

    op.create_table(
        "pricing_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contractor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_type", work_type, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "last_updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["contractor_id"],
            ["contractors.id"],
            ondelete="CASCADE",
            name="fk_pricing_configs_contractor_id_contractors",
        ),
    )
    op.create_index(
        "ix_pricing_configs_active_per_work_type",
        "pricing_configs",
        ["contractor_id", "work_type"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contractor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("buyer_phone", sa.String(length=32), nullable=False),
        sa.Column("state", session_state, nullable=False),
        sa.Column("work_type", work_type, nullable=True),
        sa.Column("collected_slots", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_slots", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["contractor_id"],
            ["contractors.id"],
            ondelete="CASCADE",
            name="fk_sessions_contractor_id_contractors",
        ),
    )
    op.create_index("ix_sessions_contractor_id", "sessions", ["contractor_id"])
    op.create_index("ix_sessions_buyer_phone", "sessions", ["buyer_phone"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", message_direction, nullable=False),
        sa.Column("message_type", message_type, nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("normalized_content", sa.Text(), nullable=True),
        sa.Column("whatsapp_message_id", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            ondelete="CASCADE",
            name="fk_messages_session_id_sessions",
        ),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.create_index(
        "ix_messages_whatsapp_message_id", "messages", ["whatsapp_message_id"]
    )

    op.create_table(
        "quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contractor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("buyer_phone", sa.String(length=32), nullable=False),
        sa.Column("work_type", work_type, nullable=False),
        sa.Column("line_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("gst_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("status", quote_status, nullable=False),
        sa.Column("pdf_url", sa.String(length=1024), nullable=True),
        sa.Column("validity_date", sa.Date(), nullable=True),
        sa.Column("pricing_config_version", sa.Integer(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            ondelete="CASCADE",
            name="fk_quotes_session_id_sessions",
        ),
        sa.ForeignKeyConstraint(
            ["contractor_id"],
            ["contractors.id"],
            ondelete="CASCADE",
            name="fk_quotes_contractor_id_contractors",
        ),
    )
    op.create_index("ix_quotes_session_id", "quotes", ["session_id"])
    op.create_index("ix_quotes_contractor_id", "quotes", ["contractor_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("contractor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["contractor_id"],
            ["contractors.id"],
            ondelete="SET NULL",
            name="fk_audit_logs_contractor_id_contractors",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            ondelete="SET NULL",
            name="fk_audit_logs_session_id_sessions",
        ),
    )
    op.create_index("ix_audit_logs_contractor_id", "audit_logs", ["contractor_id"])
    op.create_index("ix_audit_logs_session_id", "audit_logs", ["session_id"])
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_event_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_session_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_contractor_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_quotes_contractor_id", table_name="quotes")
    op.drop_index("ix_quotes_session_id", table_name="quotes")
    op.drop_table("quotes")

    op.drop_index("ix_messages_whatsapp_message_id", table_name="messages")
    op.drop_index("ix_messages_session_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_sessions_buyer_phone", table_name="sessions")
    op.drop_index("ix_sessions_contractor_id", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("ix_pricing_configs_active_per_work_type", table_name="pricing_configs")
    op.drop_table("pricing_configs")

    op.drop_table("contractors")

    for name in (
        "quote_status",
        "message_type",
        "message_direction",
        "session_state",
        "approval_mode",
        "work_type",
    ):
        op.execute(f"DROP TYPE IF EXISTS {name}")
