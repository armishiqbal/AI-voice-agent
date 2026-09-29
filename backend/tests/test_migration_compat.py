from io import StringIO

from sqlalchemy.dialects import postgresql

from app.core.migration_compat import AwaazPostgresqlImpl, widen_existing_postgresql_version_table


def test_postgresql_alembic_version_column_fits_long_revision_identifiers() -> None:
    impl = AwaazPostgresqlImpl(
        dialect=postgresql.dialect(),
        connection=None,
        as_sql=True,
        transactional_ddl=None,
        output_buffer=StringIO(),
        context_opts={},
    )

    table = impl.version_table_impl(
        version_table="alembic_version",
        version_table_schema=None,
        version_table_pk=True,
    )

    assert table.c.version_num.type.length == 128


def test_postgresql_version_table_widening_skips_sqlite_connections() -> None:
    class SQLiteConnection:
        class dialect:
            name = "sqlite"

    widen_existing_postgresql_version_table(SQLiteConnection())  # type: ignore[arg-type]
