from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("properties", sa.Column("id", sa.String(64), primary_key=True), sa.Column("title", sa.String(255), nullable=False), sa.Column("city", sa.String(64), nullable=False), sa.Column("area", sa.String(128), nullable=False), sa.Column("purpose", sa.String(32), nullable=False), sa.Column("price_pkr", sa.Integer(), nullable=False), sa.Column("bedrooms", sa.Integer(), nullable=False), sa.Column("size_sqft", sa.Integer(), nullable=False), sa.Column("amenities", sa.JSON(), nullable=False), sa.Column("developer", sa.String(128), nullable=False), sa.Column("payment_plan", sa.Text(), nullable=False), sa.Column("available", sa.Boolean(), nullable=False), sa.Column("assigned_employee", sa.String(128), nullable=False), sa.Column("source_version", sa.String(64), nullable=False))
    op.create_table("appointments", sa.Column("id", sa.String(36), primary_key=True), sa.Column("reference", sa.String(64), nullable=False, unique=True), sa.Column("property_id", sa.String(64), nullable=False), sa.Column("employee", sa.String(128), nullable=False), sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False), sa.Column("contact_email_ciphertext", sa.Text(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("idempotency_key", sa.String(36), nullable=False, unique=True))
    op.create_table("outbox_events", sa.Column("id", sa.String(36), primary_key=True), sa.Column("event_type", sa.String(100), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))

def downgrade() -> None:
    op.drop_table("outbox_events")
    op.drop_table("appointments")
    op.drop_table("properties")
