"""imports and message source

Revision ID: 003_imports_and_message_source
Revises: 002_add_messages_chat_ts_index
Create Date: 2026-10-26 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_imports_and_message_source'
down_revision: str | None = '002_add_messages_chat_ts_index'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'imports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('file_hash', sa.Text(), nullable=False),
        sa.Column('filename', sa.Text(), nullable=False),
        sa.Column('chats', postgresql.JSONB(), nullable=False),
        sa.Column('stats', postgresql.JSONB(), nullable=False),
        sa.Column(
            'imported_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_hash', 'chats', name='uq_imports_file_hash_chats'),
    )
    op.add_column(
        'messages',
        sa.Column(
            'source',
            sa.Text(),
            server_default=sa.text("'live'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        'ck_messages_source',
        'messages',
        "source IN ('live','import')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_messages_source', 'messages', type_='check')
    op.drop_column('messages', 'source')
    op.drop_table('imports')
