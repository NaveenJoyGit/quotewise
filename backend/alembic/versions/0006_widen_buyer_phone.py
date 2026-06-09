"""widen buyer_phone for fwd:{session_id} synthetic phones (FR-002)

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-09

fwd:{uuid} is 40 characters; initial schema used VARCHAR(32).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BUYER_PHONE_LEN = 48


def upgrade() -> None:
    op.alter_column(
        "sessions",
        "buyer_phone",
        existing_type=sa.String(length=32),
        type_=sa.String(length=_BUYER_PHONE_LEN),
        existing_nullable=False,
    )
    op.alter_column(
        "quotes",
        "buyer_phone",
        existing_type=sa.String(length=32),
        type_=sa.String(length=_BUYER_PHONE_LEN),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "quotes",
        "buyer_phone",
        existing_type=sa.String(length=_BUYER_PHONE_LEN),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
    op.alter_column(
        "sessions",
        "buyer_phone",
        existing_type=sa.String(length=_BUYER_PHONE_LEN),
        type_=sa.String(length=32),
        existing_nullable=False,
    )
