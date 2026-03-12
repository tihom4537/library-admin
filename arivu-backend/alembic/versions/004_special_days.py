"""004 special_days table with Karnataka/national occasion seed data

Revision ID: 004_special_days
Revises: 003_phase5
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

revision = '004_special_days'
down_revision = '003_phase5'
branch_labels = None
depends_on = None

# (month, day, occasion_kn, occasion_en)
_SYSTEM_DAYS = [
    (1, 26, "ಗಣರಾಜ್ಯೋತ್ಸವ", "Republic Day"),
    (1, 30, "ಹುತಾತ್ಮರ ದಿನ", "Martyrs' Day"),
    (2, 28, "ರಾಷ್ಟ್ರೀಯ ವಿಜ್ಞಾನ ದಿನ", "National Science Day"),
    (3, 8,  "ಅಂತರರಾಷ್ಟ್ರೀಯ ಮಹಿಳಾ ದಿನ", "International Women's Day"),
    (4, 2,  "ವಿಶ್ವ ಆಟಿಸಂ ಜಾಗೃತಿ ದಿನ", "World Autism Awareness Day"),
    (4, 22, "ಭೂ ದಿನ", "Earth Day"),
    (4, 23, "ವಿಶ್ವ ಪುಸ್ತಕ ದಿನ", "World Book Day"),
    (5, 1,  "ಕಾರ್ಮಿಕರ ದಿನ", "Labour Day"),
    (6, 5,  "ವಿಶ್ವ ಪರಿಸರ ದಿನ", "World Environment Day"),
    (6, 21, "ಅಂತರರಾಷ್ಟ್ರೀಯ ಯೋಗ ದಿನ", "International Yoga Day"),
    (7, 11, "ವಿಶ್ವ ಜನಸಂಖ್ಯಾ ದಿನ", "World Population Day"),
    (8, 15, "ಸ್ವಾತಂತ್ರ್ಯ ದಿನ", "Independence Day"),
    (8, 29, "ರಾಷ್ಟ್ರೀಯ ಕ್ರೀಡಾ ದಿನ", "National Sports Day"),
    (9, 5,  "ಶಿಕ್ಷಕರ ದಿನ", "Teachers' Day"),
    (9, 8,  "ವಿಶ್ವ ಸಾಕ್ಷರತೆ ದಿನ", "International Literacy Day"),
    (10, 2, "ಗಾಂಧಿ ಜಯಂತಿ", "Gandhi Jayanti"),
    (10, 16,"ವಿಶ್ವ ಆಹಾರ ದಿನ", "World Food Day"),
    (11, 1, "ಕರ್ನಾಟಕ ರಾಜ್ಯೋತ್ಸವ", "Karnataka Rajyotsava"),
    (11, 14,"ಮಕ್ಕಳ ದಿನ", "Children's Day"),
    (11, 19,"ವಿಶ್ವ ಶೌಚಾಲಯ ದಿನ", "World Toilet Day"),
    (12, 1, "ವಿಶ್ವ ಏಡ್ಸ್ ದಿನ", "World AIDS Day"),
    (12, 10,"ಮಾನವ ಹಕ್ಕುಗಳ ದಿನ", "Human Rights Day"),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'special_day' not in inspector.get_table_names():
        op.create_table(
            'special_day',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('month', sa.Integer(), nullable=False),
            sa.Column('day', sa.Integer(), nullable=False),
            sa.Column('year', sa.Integer(), nullable=True),
            sa.Column('occasion_kn', sa.String(200), nullable=False),
            sa.Column('occasion_en', sa.String(200), nullable=False),
            sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        )
        op.create_index('ix_special_day_month_day', 'special_day', ['month', 'day'])

        # Seed system special days
        bind.execute(
            sa.text(
                "INSERT INTO special_day (id, month, day, year, occasion_kn, occasion_en, is_system) "
                "VALUES (:id, :month, :day, :year, :kn, :en, true)"
            ),
            [
                {"id": str(uuid.uuid4()), "month": m, "day": d, "year": None, "kn": kn, "en": en}
                for m, d, kn, en in _SYSTEM_DAYS
            ],
        )

    # Also add 'mandatory' column to circular_action_item if missing
    col_names = [c['name'] for c in inspector.get_columns('circular_action_item')]
    if 'mandatory' not in col_names:
        op.add_column(
            'circular_action_item',
            sa.Column('mandatory', sa.Boolean(), nullable=False, server_default='true'),
        )


def downgrade() -> None:
    op.drop_index('ix_special_day_month_day', table_name='special_day', if_exists=True)
    op.drop_table('special_day', if_exists=True)
    # Note: we intentionally leave the mandatory column in circular_action_item on downgrade
