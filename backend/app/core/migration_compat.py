"""PostgreSQL-specific Alembic compatibility for long revision identifiers."""

from alembic.ddl.postgresql import PostgresqlImpl
from sqlalchemy import String, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.schema import Table


class AwaazPostgresqlImpl(PostgresqlImpl):
    """Keep Alembic's version column large enough for this repository's revision IDs."""

    __dialect__ = "postgresql"

    def version_table_impl(
        self,
        *,
        version_table: str,
        version_table_schema: str | None,
        version_table_pk: bool,
        **kwargs: object,
    ) -> Table:
        table = super().version_table_impl(
            version_table=version_table,
            version_table_schema=version_table_schema,
            version_table_pk=version_table_pk,
            **kwargs,
        )
        table.c.version_num.type = String(128)
        return table


def widen_existing_postgresql_version_table(connection: Connection) -> None:
    """Idempotently widen Alembic's existing column before storing a long revision ID."""

    if connection.dialect.name != "postgresql":
        return
    if inspect(connection).has_table("alembic_version"):
        connection.execute(
            text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)")
        )
    # Inspection triggers SQLAlchemy autobegin; finish that preflight transaction before Alembic
    # opens its own migration transaction. This also commits the widened column when present.
    connection.commit()
