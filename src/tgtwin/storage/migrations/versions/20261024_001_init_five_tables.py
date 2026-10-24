"""init five tables

Revision ID: 001_init_five_tables
Revises: 
Create Date: 2025-10-24 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '001_init_five_tables'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('mode', sa.Text(), nullable=False),
        sa.Column('persona_id', sa.Integer(), nullable=True),
        sa.Column('overrides', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'contacts',
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=True),
        sa.Column('group_id', sa.Integer(), nullable=True),
        sa.Column('mode', sa.Text(), nullable=True),
        sa.Column('persona_id', sa.Integer(), nullable=True),
        sa.Column('overrides', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('chat_id'),
    )
    op.create_table(
        'personas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('tg_message_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('connection_id', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chat_id', 'tg_message_id', name='uq_messages_chat_tg'),
        sa.CheckConstraint("role IN ('them','owner','bot')", name='ck_messages_role'),
    )
    op.create_table(
        'reply_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('trigger_message_id', sa.Integer(), nullable=True),
        sa.Column('mode', sa.Text(), nullable=True),
        sa.Column('reply', sa.Text(), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('sent', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('ts', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('reply_log')
    op.drop_table('messages')
    op.drop_table('personas')
    op.drop_table('contacts')
    op.drop_table('groups')
