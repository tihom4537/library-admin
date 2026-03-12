"""003 phase5 weekly nudge table

Revision ID: 003_phase5
Revises: 002_phase3
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003_phase5'
down_revision = '002_phase3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'weekly_nudge' not in inspector.get_table_names():
        op.create_table(
            'weekly_nudge',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('week_start_date', sa.Date(), nullable=False),
            sa.Column('nudge_type', sa.String(30), nullable=False),
            sa.Column('content_kn', sa.Text(), nullable=False),
            sa.Column('content_en', sa.Text(), nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
            sa.Column('generated_by', sa.String(10), nullable=False, server_default='manual'),
            sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('sent_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        )
        op.create_index('ix_weekly_nudge_week_start_date', 'weekly_nudge', ['week_start_date'])


def downgrade() -> None:
    op.drop_index('ix_weekly_nudge_week_start_date', table_name='weekly_nudge', if_exists=True)
    op.drop_table('weekly_nudge', if_exists=True)
