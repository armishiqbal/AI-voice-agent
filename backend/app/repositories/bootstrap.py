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
        "appointments": {"contact_phone_ciphertext": "TEXT"},
        "conversation_states": {
            "tool_results": "JSON NOT NULL DEFAULT '{}'",
            "bedrooms": "INTEGER",
            "amenities": "JSON NOT NULL DEFAULT '[]'",
            "investment_goal": "VARCHAR(100)",
        },
        "properties": {"investment_goals": "JSON NOT NULL DEFAULT '[]'"},
        "leads": {
            "follow_up_at": "DATETIME",
            "follow_up_enqueued_at": "DATETIME",
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
