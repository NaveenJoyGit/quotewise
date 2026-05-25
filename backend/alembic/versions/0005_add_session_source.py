"""add session source for contractor-forward quotes (FR-002)

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SESSION_SOURCE = ("buyer_direct", "contractor_forward")


def upgrade() -> None:
    session_source = postgresql.ENUM(*SESSION_SOURCE, name="session_source")
    session_source.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "sessions",
        sa.Column(
            "source",
            session_source,
            nullable=False,
            server_default="buyer_direct",
        ),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "forward_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("sessions", "forward_metadata")
    op.drop_column("sessions", "source")
    op.execute("DROP TYPE IF EXISTS session_source")
