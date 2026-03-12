"""005 add March festival and national observance days

Revision ID: 005_march_festivals
Revises: 004_special_days
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = '005_march_festivals'
down_revision = '004_special_days'
branch_labels = None
depends_on = None

# Fixed annual observances (year=NULL → recurring every year)
_FIXED_DAYS = [
    (3, 4,  "ರಾಷ್ಟ್ರೀಯ ಸುರಕ್ಷತಾ ದಿನ",  "National Safety Day"),
    (3, 16, "ರಾಷ್ಟ್ರೀಯ ಲಸಿಕಾ ದಿನ",     "National Vaccination Day"),
    (3, 23, "ಶಹೀದ್ ದಿವಸ",               "Shaheed Diwas"),
]

# 2026-specific festival dates (lunar calendar — changes every year)
_YEAR_2026 = [
    (3,  3, 2026, "ಹೋಳಿಕಾ ದಹನ",         "Holika Dahan"),
    (3,  4, 2026, "ಹೋಳಿ",                "Holi"),
    (3, 19, 2026, "ಚೈತ್ರ ನವರಾತ್ರಿ",      "Chaitra Navratri"),
    (3, 27, 2026, "ರಾಮ ನವಮಿ",            "Ram Navami"),
    (3, 30, 2026, "ಉಗಾದಿ / ಗುಡಿ ಪಡ್ವಾ", "Ugadi / Gudi Padwa"),
]


def upgrade() -> None:
    bind = op.get_bind()

    # Helper: skip if month+day+year combo already exists
    def _insert_if_missing(month, day, year, kn, en):
        if year is None:
            exists = bind.execute(
                sa.text(
                    "SELECT 1 FROM special_day WHERE month=:m AND day=:d AND year IS NULL AND occasion_en=:en"
                ),
                {"m": month, "d": day, "en": en},
            ).fetchone()
        else:
            exists = bind.execute(
                sa.text(
                    "SELECT 1 FROM special_day WHERE month=:m AND day=:d AND year=:y AND occasion_en=:en"
                ),
                {"m": month, "d": day, "y": year, "en": en},
            ).fetchone()
        if not exists:
            bind.execute(
                sa.text(
                    "INSERT INTO special_day (id, month, day, year, occasion_kn, occasion_en, is_system) "
                    "VALUES (:id, :m, :d, :y, :kn, :en, true)"
                ),
                {"id": str(uuid.uuid4()), "m": month, "d": day, "y": year, "kn": kn, "en": en},
            )

    for m, d, kn, en in _FIXED_DAYS:
        _insert_if_missing(m, d, None, kn, en)

    for m, d, y, kn, en in _YEAR_2026:
        _insert_if_missing(m, d, y, kn, en)


def downgrade() -> None:
    bind = op.get_bind()
    names = [en for _, _, en in _FIXED_DAYS] + [en for _, _, _, _, en in _YEAR_2026]
    for en in names:
        bind.execute(
            sa.text("DELETE FROM special_day WHERE occasion_en=:en AND is_system=true"),
            {"en": en},
        )
