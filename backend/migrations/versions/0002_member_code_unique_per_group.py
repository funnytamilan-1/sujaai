"""Allow the same member code in different chit groups.

Revision ID: 0002_member_code_unique_per_group
Revises: 0001_sujaai_schema_baseline
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_member_code_unique_per_group"
down_revision = "0001_sujaai_schema_baseline"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("chit_members")}

    # The previous index enforced global uniqueness. Replace it with a
    # normal lookup index plus a composite unique index scoped to group_id.
    if "ix_chit_members_member_code" in indexes:
        op.drop_index("ix_chit_members_member_code", table_name="chit_members")

    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("chit_members")}
    if "ix_chit_members_member_code" not in indexes:
        op.create_index("ix_chit_members_member_code", "chit_members", ["member_code"], unique=False)
    if "uq_chit_members_group_member_code" not in indexes:
        op.create_index(
            "uq_chit_members_group_member_code",
            "chit_members",
            ["group_id", "member_code"],
            unique=True,
        )


def downgrade():
    bind = op.get_bind()
    duplicate = bind.execute(sa.text(
        "SELECT member_code FROM chit_members GROUP BY member_code HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if duplicate:
        raise RuntimeError(
            "Cannot restore global member-code uniqueness: at least one member code "
            "is used in more than one chit group."
        )

    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("chit_members")}
    if "uq_chit_members_group_member_code" in indexes:
        op.drop_index("uq_chit_members_group_member_code", table_name="chit_members")
    if "ix_chit_members_member_code" in indexes:
        op.drop_index("ix_chit_members_member_code", table_name="chit_members")
    op.create_index("ix_chit_members_member_code", "chit_members", ["member_code"], unique=True)
