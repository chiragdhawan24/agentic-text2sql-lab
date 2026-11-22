import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

from app import initialize_db, total_revenue


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        self.db_path = Path(temp_dir.name) / "test.db"
        initialize_db(self.db_path)

    def test_expected_tables_exist(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            with connection:
                tables = {
                    row[0] for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }

        self.assertEqual(
            tables,
            {"customers", "orders", "products", "order_items"}
        )

    def test_total_revenue(self):
        self.assertAlmostEqual(
            total_revenue(self.db_path), 320.00
        )

    def test_setup_is_repeatable(self):
        initialize_db(self.db_path)

        with closing(sqlite3.connect(self.db_path)) as connection:
            with connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM order_items"
                ).fetchone()[0]

        self.assertEqual(count, 3)


if __name__ == "__main__":
    unittest.main()