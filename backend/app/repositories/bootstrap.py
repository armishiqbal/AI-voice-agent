from app.repositories import records  # noqa: F401
from app.repositories.database import Base, engine


def create_schema_for_local_development() -> None:
    """Development-only bootstrap; production uses Alembic migrations."""
    Base.metadata.create_all(bind=engine)
    # ``create_all`` does not alter an existing SQLite database. Keep the
    # zero-setup local command compatible with databases created before a
    # non-destructive nullable/JSON field was introduced; production still
    # uses the explicit Alembic chain.
    if engine.dialect.name != "sqlite":
        return
    additions = {
        "appointments": {"contact_phone_ciphertext": "TEXT", "organization_id": "VARCHAR(36)", "agent_subject": "VARCHAR(128)", "closed_at": "DATETIME"},
        "conversation_states": {
            "tool_results": "JSON NOT NULL DEFAULT '{}'",
            "bedrooms": "INTEGER",
            "amenities": "JSON NOT NULL DEFAULT '[]'",
            "investment_goal": "VARCHAR(100)",
        },
        "properties": {
            "organization_id": "VARCHAR(36)", "classification": "VARCHAR(16)", "rental_period": "VARCHAR(16)", "coordinates_approved_at": "DATETIME",
            "investment_goals": "JSON NOT NULL DEFAULT '[]'",
            "assigned_staff_id": "VARCHAR(128)",
            "slug": "VARCHAR(180)",
            "description": "TEXT NOT NULL DEFAULT ''",
            "transaction_type": "VARCHAR(16)",
            "property_type": "VARCHAR(24)",
            "bathrooms": "INTEGER",
            "publication_status": "VARCHAR(16) NOT NULL DEFAULT 'draft'",
            "availability_status": "VARCHAR(20) NOT NULL DEFAULT 'unconfirmed'",
            "availability_confirmed_at": "DATETIME",
            "content_permission_confirmed_at": "DATETIME",
            "edit_version": "INTEGER NOT NULL DEFAULT 1",
            "published_at": "DATETIME",
            "latitude": "FLOAT",
            "longitude": "FLOAT",
        },
        "leads": {
            "follow_up_at": "DATETIME",
            "follow_up_enqueued_at": "DATETIME",
        },
        "website_inquiries": {
            "organization_id": "VARCHAR(36)", "agent_subject": "VARCHAR(128)",
            "assigned_staff_id": "VARCHAR(128)",
            "follow_up_at": "DATETIME",
            "closing_outcome": "VARCHAR(64)",
        },
    }
    with engine.begin() as connection:
        for table, columns in additions.items():
            present = {
                row[1]
                for row in connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            }
            for column, definition in columns.items():
                if column not in present:
                    connection.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                    )
