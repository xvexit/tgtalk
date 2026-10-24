"""add messages chat ts index

Revision ID: 002_add_messages_chat_ts_index
Revises: 001_init_five_tables
Create Date: 2025-10-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '002_add_messages_chat_ts_index'
down_revision: Union[str, None] = '001_init_five_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages (chat_id, ts)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_messages_chat_ts")
