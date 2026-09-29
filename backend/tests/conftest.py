"""Give every pytest run a disposable database instead of the developer's .env DB."""

from __future__ import annotations

import atexit
import os
from pathlib import Path
from tempfile import gettempdir

_postgres_test_database_url = os.getenv("TEST_DATABASE_URL")
_test_database = Path(gettempdir()) / f"awaaz-pytest-{os.getpid()}.sqlite3"
if _postgres_test_database_url:
    os.environ["DATABASE_URL"] = _postgres_test_database_url
else:
    os.environ["DATABASE_URL"] = f"sqlite:///{_test_database.as_posix()}"


def _remove_test_database() -> None:
    if _postgres_test_database_url:
        return
    for suffix in ("", "-wal", "-shm"):
        Path(f"{_test_database}{suffix}").unlink(missing_ok=True)


atexit.register(_remove_test_database)
