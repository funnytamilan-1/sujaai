"""Create any missing SUJAAI tables as a safe initial schema baseline.

This baseline is intentionally non-destructive for databases that already contain
SUJAAI tables. Future schema changes must be added as new Alembic revisions.
"""
from alembic import op

from app import models  # noqa: F401 — register models
from app.database import Base

revision = "0001_sujaai_schema_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    # Intentionally retain production data. Write explicit reversible migrations
    # for future schema changes instead of dropping all application tables.
    pass
