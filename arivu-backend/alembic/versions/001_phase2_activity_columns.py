"""phase2: add new columns to activity_template and scheduled_activity

Revision ID: 001_phase2
Revises:
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '001_phase2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── activity_template ─────────────────────────────────────────────────────
    op.add_column('activity_template', sa.Column('min_children', sa.Integer(), nullable=True))
    op.add_column('activity_template', sa.Column('max_children', sa.Integer(), nullable=True))
    op.add_column('activity_template', sa.Column('steps_kn', JSONB(), nullable=True))
    op.add_column('activity_template', sa.Column('reference_image_urls', JSONB(), nullable=True))
    op.add_column('activity_template', sa.Column(
        'status', sa.String(20), nullable=False, server_default='published'
    ))
    op.add_column('activity_template', sa.Column(
        'updated_at', sa.DateTime(timezone=True),
        nullable=False, server_default=sa.text('NOW()')
    ))

    # ── scheduled_activity ────────────────────────────────────────────────────
    op.add_column('scheduled_activity', sa.Column(
        'circular_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
    ))
    op.add_column('scheduled_activity', sa.Column('circular_reference', sa.String(100), nullable=True))
    op.add_column('scheduled_activity', sa.Column(
        'immediate_sent', sa.Boolean(), nullable=False, server_default='false'
    ))
    op.add_column('scheduled_activity', sa.Column(
        'created_by_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True
    ))

    # ── micro_learning_module — add per-step image URLs + published flag ───────
    op.add_column('micro_learning_module', sa.Column('step_one_image_url', sa.Text(), nullable=True))
    op.add_column('micro_learning_module', sa.Column('step_two_image_url', sa.Text(), nullable=True))
    op.add_column('micro_learning_module', sa.Column('step_three_image_url', sa.Text(), nullable=True))
    op.add_column('micro_learning_module', sa.Column(
        'published', sa.Boolean(), nullable=False, server_default='false'
    ))
    op.add_column('micro_learning_module', sa.Column(
        'updated_at', sa.DateTime(timezone=True),
        nullable=False, server_default=sa.text('NOW()')
    ))


def downgrade() -> None:
    op.drop_column('micro_learning_module', 'updated_at')
    op.drop_column('micro_learning_module', 'published')
    op.drop_column('micro_learning_module', 'step_three_image_url')
    op.drop_column('micro_learning_module', 'step_two_image_url')
    op.drop_column('micro_learning_module', 'step_one_image_url')
    op.drop_column('scheduled_activity', 'created_by_id')
    op.drop_column('scheduled_activity', 'immediate_sent')
    op.drop_column('scheduled_activity', 'circular_reference')
    op.drop_column('scheduled_activity', 'circular_id')
    op.drop_column('activity_template', 'updated_at')
    op.drop_column('activity_template', 'status')
    op.drop_column('activity_template', 'reference_image_urls')
    op.drop_column('activity_template', 'steps_kn')
    op.drop_column('activity_template', 'max_children')
    op.drop_column('activity_template', 'min_children')
