from alembic import op
import sqlalchemy as sa


revision = "0005_import_provenance"
down_revision = "0004_employee_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("source", sa.String(255), nullable=False, server_default="demo-fixture"))
    op.add_column("properties", sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "property_import_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", sa.String(255), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("property_import_batches")
    op.drop_column("properties", "imported_at")
    op.drop_column("properties", "source")
