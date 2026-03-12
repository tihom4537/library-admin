"""phase3: create circular, circular_action_item tables

Revision ID: 002_phase3
Revises: 001_phase2
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '002_phase3'
down_revision = '001_phase2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = inspector.get_table_names()

    if 'circular' not in existing:
        op.create_table(
            'circular',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('circular_number', sa.String(50), nullable=False),
            sa.Column('issue_date', sa.Date(), nullable=True),
            sa.Column('original_text', sa.Text(), nullable=True),
            sa.Column('simplified_text', sa.Text(), nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
            sa.Column('created_by_id', UUID(as_uuid=True), nullable=True),
            sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('sent_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('NOW()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('NOW()')),
        )

    if 'circular_action_item' not in existing:
        op.create_table(
            'circular_action_item',
            sa.Column('id', UUID(as_uuid=True), primary_key=True),
            sa.Column('circular_id', UUID(as_uuid=True), nullable=False),
            sa.Column('activity_template_id', UUID(as_uuid=True), nullable=True),
            sa.Column('title_kn', sa.String(300), nullable=False),
            sa.Column('due_date', sa.Date(), nullable=True),
            sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        )
        op.create_index('ix_circular_action_item_circular_id',
                        'circular_action_item', ['circular_id'])


def downgrade() -> None:
    op.drop_index('ix_circular_action_item_circular_id',
                  table_name='circular_action_item', if_exists=True)
    op.drop_table('circular_action_item', if_exists=True)
    op.drop_table('circular', if_exists=True)
