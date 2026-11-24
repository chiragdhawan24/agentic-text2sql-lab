import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from app import DB_PATH


def execute_read_only_sql(
    sql: str,
    db_path: Path = DB_PATH,
    max_rows: int = 100,
    timeout_seconds: float = 2.0,
) -> dict:
    """Execute one read-only SQLite SELECT query."""

    # Reject statements that don't begin with SELECT or WITH.
    if not re.match(r"^\s*(SELECT|WITH)\b", sql, re.IGNORECASE):
        raise ValueError("Only SELECT queries are allowed")

    if max_rows < 1 or timeout_seconds <= 0:
        raise ValueError("Row limit and timeout must be positive")

    if not db_path.is_file():
        raise FileNotFoundError(f"Database does not exist: {db_path}")

    uri = f"{db_path.resolve().as_uri()}?mode=ro"

    # SQLite-level authorization: allow only read operations.
    def authorizer(action, arg1, arg2, database, source):
        allowed = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_READ,
            sqlite3.SQLITE_FUNCTION,
        }

        if action == sqlite3.SQLITE_FUNCTION:
            if (arg2 or "").lower() == "load_extension":
                return sqlite3.SQLITE_DENY

        return (
            sqlite3.SQLITE_OK
            if action in allowed
            else sqlite3.SQLITE_DENY
        )

    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.execute("PRAGMA query_only = ON")
        connection.set_authorizer(authorizer)

        started = time.monotonic()

        connection.set_progress_handler(
            lambda: int(
                time.monotonic() - started >= timeout_seconds
            ),
            1000,
        )

        # execute() accepts only one SQL statement.
        cursor = connection.execute(sql)

        if cursor.description is None:
            raise ValueError("Query must return rows")

        columns = [col[0] for col in cursor.description]
        results = cursor.fetchmany(max_rows + 1)

        return {
            "columns": columns,
            "rows": [list(row) for row in results[:max_rows]],
            "truncated": len(results) > max_rows,
        }