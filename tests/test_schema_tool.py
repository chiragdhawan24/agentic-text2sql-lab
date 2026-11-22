import tempfile
import unittest
from pathlib import Path

from app import initialize_db
from schema_tool import inspect_database_schema


class SchemaToolTests(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        self.db_path = Path(temp_dir.name) / "test.db"
        initialize_db(self.db_path)

    def test_discovers_all_tables(self):
        schema = inspect_database_schema(self.db_path)

        self.assertEqual(
            set(schema.keys()),
            {"customers", "orders", "products", "order_items"}
        )

    def test_discovers_columns(self):
        schema = inspect_database_schema(self.db_path)

        columns = {
            col["name"] for col in schema["customers"]["columns"]
        }

        self.assertEqual(columns, {"customer_id", "name"})

    def test_discovers_foreign_keys(self):
        schema = inspect_database_schema(self.db_path)

        foreign_keys = schema["order_items"]["foreign_keys"]

        relationships = {
            (fk["column"], fk["references_table"])
            for fk in foreign_keys
        }

        self.assertIn(("order_id", "orders"), relationships)
        self.assertIn(("product_id", "products"), relationships)

    def test_missing_database_raises_error(self):
        missing_path = self.db_path.parent / "missing.db"

        with self.assertRaises(FileNotFoundError):
            inspect_database_schema(missing_path)


if __name__ == "__main__":
    unittest.main()