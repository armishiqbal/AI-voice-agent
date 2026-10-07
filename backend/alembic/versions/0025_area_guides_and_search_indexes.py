"""Add area guides table and composite search indexes.

Revision ID: 0025_area_guides_and_search_indexes
Revises: 0024_public_property_catalog
"""

import sqlalchemy as sa
from alembic import op

revision = "0025_area_guides_and_search_indexes"
down_revision = "0024_public_property_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "area_guides",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("city_slug", sa.String(length=64), nullable=False),
        sa.Column("area_slug", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("overview_markdown", sa.Text(), server_default="", nullable=False),
        sa.Column("amenities_summary", sa.Text(), server_default="", nullable=False),
        sa.Column("transport_info", sa.Text(), server_default="", nullable=False),
        sa.Column("investment_outlook", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "publication_status", sa.String(length=16), server_default="draft", nullable=False
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_id", sa.String(length=128), nullable=True),
        sa.Column("sources_json", sa.JSON(), server_default="[]", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "uq_area_guides_city_area",
        "area_guides",
        ["city_slug", "area_slug"],
        unique=True,
    )
    op.create_index("ix_area_guides_city_slug", "area_guides", ["city_slug"])
    op.create_index("ix_area_guides_area_slug", "area_guides", ["area_slug"])
    op.create_index("ix_area_guides_status", "area_guides", ["publication_status"])

    op.create_index(
        "ix_properties_faceted_search",
        "properties",
        ["publication_status", "availability_status", "city", "transaction_type", "price_pkr"],
    )


def downgrade() -> None:
    op.drop_index("ix_properties_faceted_search", table_name="properties")
    op.drop_table("area_guides")
