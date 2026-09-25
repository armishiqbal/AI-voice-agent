from app.repositories import records  # noqa: F401
from app.repositories.database import Base, engine


def create_schema_for_local_development() -> None:
    """Development-only bootstrap; production uses Alembic migrations."""
    Base.metadata.create_all(bind=engine)
    # ``create_all`` does not alter an existing SQLite demo database. Keep the
    # zero-setup developer command compatible with databases created before a
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
        "leads": {"follow_up_at": "DATETIME"},
    }
    with engine.begin() as connection:
        property_columns: set[str] = set()
        for table, columns in additions.items():
            present = {
                row[1]
                for row in connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            }
            if table == "properties":
                property_columns = present | set(columns)
            for column, definition in columns.items():
                if column not in present:
                    connection.exec_driver_sql(
                        f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                    )
        # Backfill only untouched demo fixtures. Imported company records keep
        # their source-authored investment metadata unchanged.
        if {"source", "purpose", "investment_goals"}.issubset(property_columns):
            connection.exec_driver_sql(
                'UPDATE properties SET investment_goals = \'["rental yield", "capital appreciation"]\' '
                "WHERE source = 'demo-fixture' AND purpose = 'investment' "
                "AND (investment_goals IS NULL OR investment_goals = '[]')"
            )
            connection.exec_driver_sql(
                "UPDATE properties SET investment_goals = '[\"capital appreciation\"]' "
                "WHERE source = 'demo-fixture' AND purpose <> 'investment' "
                "AND (investment_goals IS NULL OR investment_goals = '[]')"
            )
