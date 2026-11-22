import json
import sqlite3
from pathlib import Path
from contextlib import closing

from app import DB_PATH


def inspect_database_schema(db_path: Path = DB_PATH) -> dict:
    if not db_path.is_file():
        raise FileNotFoundError(f"Database does not exist: {db_path}")

    schema = {}
    uri = f"{db_path.resolve().as_uri()}?mode=ro"

    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            connection.row_factory = sqlite3.Row

            tables = connection.execute("""
                SELECT name FROM sqlite_master
                WHERE type = 'table'
                AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """).fetchall()

            for row in tables:
                table_name = row["name"]
                quoted_name = '"' + table_name.replace('"', '""') + '"'

                columns = connection.execute(
                    f"PRAGMA table_info({quoted_name})"
                )

                foreign_keys = connection.execute(
                    f"PRAGMA foreign_key_list({quoted_name})"
                )

                schema[table_name] = {
                    "columns": [
                        {
                            "name": col["name"],
                            "type": col["type"],
                            "primary_key": bool(col["pk"])
                        }
                        for col in columns
                    ],
                    "foreign_keys": [
                        {
                            "column": fk["from"],
                            "references_table": fk["table"],
                            "references_column": fk["to"]
                        }
                        for fk in foreign_keys
                    ]
                }

    return schema


if __name__ == "__main__":
    print(json.dumps(inspect_database_schema(), indent=2))