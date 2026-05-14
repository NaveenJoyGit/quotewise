"""add api_key to contractors

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contractors",
        sa.Column(
            "api_key",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )
    op.create_index(
        "ix_contractors_api_key",
        "contractors",
        ["api_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_contractors_api_key", table_name="contractors")
    op.drop_column("contractors", "api_key")
