from alembic import op
import sqlalchemy as sa


revision = "0012_property_local_services"
down_revision = "0011_conversation_state_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("nearby_schools", sa.JSON(), nullable=True))
    op.add_column("properties", sa.Column("nearby_hospitals", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("properties", "nearby_hospitals")
    op.drop_column("properties", "nearby_schools")
