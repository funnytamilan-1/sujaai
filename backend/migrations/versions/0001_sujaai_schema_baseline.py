"""Create the initial SUJAAI schema without dropping existing data.

This revision is intentionally static. Future model changes belong in new,
immutable Alembic revisions rather than edits to this baseline.
"""
import sqlalchemy as sa
from alembic import op

revision = "0001_sujaai_schema_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "chit_groups" not in tables:
        op.create_table(
            "chit_groups",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("group_code", sa.String(length=40), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("chit_type", sa.String(length=12), nullable=False),
            sa.Column("default_amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "chit_members" not in tables:
        op.create_table(
            "chit_members",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("member_code", sa.String(length=60), nullable=False),
            sa.Column("group_id", sa.Integer(), sa.ForeignKey("chit_groups.id"), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("mobile", sa.String(length=20), nullable=False),
            sa.Column("address", sa.Text(), nullable=False),
            sa.Column("joining_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "chit_payments" not in tables:
        op.create_table(
            "chit_payments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("payment_ref", sa.String(length=64), nullable=False),
            sa.Column("member_id", sa.Integer(), sa.ForeignKey("chit_members.id"), nullable=False),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("frequency", sa.String(length=12), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("recorded_by", sa.String(length=160), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "application_audit_logs" not in tables:
        op.create_table(
            "application_audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("actor", sa.String(length=160), nullable=False),
            sa.Column("action", sa.String(length=80), nullable=False),
            sa.Column("entity_type", sa.String(length=40), nullable=False),
            sa.Column("entity_id", sa.String(length=80), nullable=False),
            sa.Column("details", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "app_users" not in tables:
        op.create_table(
            "app_users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(length=190), nullable=False),
            sa.Column("password_hash", sa.String(length=256), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )

    if "saved_designs" not in tables:
        op.create_table(
            "saved_designs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_email", sa.String(length=190), nullable=False),
            sa.Column("design_type", sa.String(length=16), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("data", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )

    indexes = [
        ("chit_groups", "ix_chit_groups_group_code", ["group_code"], True),
        ("chit_groups", "ix_chit_groups_name", ["name"], True),
        ("chit_members", "ix_chit_members_member_code", ["member_code"], True),
        ("chit_members", "ix_chit_members_group_id", ["group_id"], False),
        ("chit_members", "ix_chit_members_name", ["name"], False),
        ("chit_members", "ix_chit_members_mobile", ["mobile"], False),
        ("chit_payments", "ix_chit_payments_payment_ref", ["payment_ref"], True),
        ("chit_payments", "ix_chit_payments_member_id", ["member_id"], False),
        ("chit_payments", "ix_chit_payments_paid_at", ["paid_at"], False),
        ("chit_payments", "ix_payment_paid_at_member", ["paid_at", "member_id"], False),
        ("app_users", "ix_app_users_email", ["email"], True),
        ("saved_designs", "ix_saved_designs_owner_email", ["owner_email"], False),
        ("saved_designs", "ix_saved_designs_design_type", ["design_type"], False),
    ]
    inspector = sa.inspect(bind)
    for table_name, index_name, columns, unique in indexes:
        if table_name not in inspector.get_table_names():
            continue
        existing = {item["name"] for item in inspector.get_indexes(table_name)}
        if index_name not in existing:
            op.create_index(index_name, table_name, columns, unique=unique)


def downgrade():
    # Deliberately non-destructive: this baseline may be stamped onto an
    # existing production database containing customer and payment records.
    pass
