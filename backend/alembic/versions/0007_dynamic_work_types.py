"""dynamic_work_types

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-13 17:25:23.087261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres requires an explicit USING clause to cast an enum to varchar
    op.execute("ALTER TABLE contractor_admin_sessions ALTER COLUMN work_type TYPE VARCHAR(64) USING work_type::text;")
    op.execute("ALTER TABLE pricing_configs ALTER COLUMN work_type TYPE VARCHAR(64) USING work_type::text;")
    op.execute("ALTER TABLE sessions ALTER COLUMN work_type TYPE VARCHAR(64) USING work_type::text;")
    op.execute("ALTER TABLE quotes ALTER COLUMN work_type TYPE VARCHAR(64) USING work_type::text;")

    # Drop the enum type from postgres
    op.execute("DROP TYPE IF EXISTS work_type CASCADE;")


def downgrade() -> None:
    # Note: downgrade might fail if new work_types were added
    # 1. Recreate enum type
    op.execute("CREATE TYPE work_type AS ENUM ('painting', 'false_ceiling');")
    
    # 2. Alter columns back to enum
    op.execute("ALTER TABLE contractor_admin_sessions ALTER COLUMN work_type TYPE work_type USING work_type::work_type;")
    op.execute("ALTER TABLE pricing_configs ALTER COLUMN work_type TYPE work_type USING work_type::work_type;")
    op.execute("ALTER TABLE sessions ALTER COLUMN work_type TYPE work_type USING work_type::work_type;")
    op.execute("ALTER TABLE quotes ALTER COLUMN work_type TYPE work_type USING work_type::work_type;")
