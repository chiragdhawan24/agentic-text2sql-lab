import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import initialize_db
from sql_tool import execute_read_only_sql


class SqlToolTests(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        self.db_path = Path(temp_dir.name) / "test.db"
        initialize_db(self.db_path)

    def test_total_revenue(self):
        result = execute_read_only_sql(
            "SELECT SUM(quantity * unit_price) AS revenue "
            "FROM order_items",
            self.db_path,
        )

        self.assertEqual(result["columns"], ["revenue"])
        self.assertEqual(result["rows"], [[320.0]])

    def test_join_query(self):
        result = execute_read_only_sql(
            "SELECT c.name FROM customers c "
            "JOIN orders o ON c.customer_id = o.customer_id "
            "ORDER BY c.name",
            self.db_path,
        )

        self.assertEqual(result["rows"], [["Ava"], ["Noah"]])

    def test_common_table_expression(self):
        result = execute_read_only_sql(
            "WITH x AS (SELECT 4 AS n) SELECT n FROM x",
            self.db_path,
        )

        self.assertEqual(result["rows"], [[4]])

    def test_rejects_data_modifications(self):
        unsafe_queries = [
            "DELETE FROM customers",
            "UPDATE customers SET name = 'X'",
            "DROP TABLE customers",
            "INSERT INTO customers VALUES (3, 'Test')",
            "PRAGMA query_only = OFF",
            "ATTACH DATABASE ':memory:' AS extra",
            "WITH x AS (SELECT 1) DELETE FROM customers",
        ]

        for query in unsafe_queries:
            with self.subTest(query=query):
                with self.assertRaises(
                    (ValueError, sqlite3.DatabaseError)
                ):
                    execute_read_only_sql(query, self.db_path)

        with sqlite3.connect(self.db_path) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM customers"
            ).fetchone()[0]

        self.assertEqual(count, 2)

    def test_rejects_multiple_statements(self):
        with self.assertRaises(sqlite3.ProgrammingError):
            execute_read_only_sql(
                "SELECT 1; DELETE FROM customers",
                self.db_path,
            )

    def test_row_limit(self):
        result = execute_read_only_sql(
            "SELECT name FROM customers ORDER BY name",
            self.db_path,
            max_rows=1,
        )

        self.assertEqual(result["rows"], [["Ava"]])
        self.assertTrue(result["truncated"])

    def test_rejects_extension_loading(self):
        with self.assertRaises(sqlite3.DatabaseError):
            execute_read_only_sql(
                "SELECT load_extension('example')",
                self.db_path,
            )

    def test_missing_database(self):
        with self.assertRaises(FileNotFoundError):
            execute_read_only_sql(
                "SELECT 1",
                self.db_path.parent / "missing.db",
            )

    def test_invalid_limits(self):
        with self.assertRaises(ValueError):
            execute_read_only_sql(
                "SELECT 1", self.db_path, max_rows=0
            )

        with self.assertRaises(ValueError):
            execute_read_only_sql(
                "SELECT 1", self.db_path, timeout_seconds=0
            )


if __name__ == "__main__":
    unittest.main()