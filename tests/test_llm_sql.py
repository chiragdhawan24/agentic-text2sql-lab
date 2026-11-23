import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app import initialize_db
from llm_sql import generate_sql


class LlmSqlTests(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        self.db_path = Path(temp_dir.name) / "test.db"
        initialize_db(self.db_path)

        self.client = Mock()

        self.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="SELECT name FROM customers;"
                    )
                )
            ]
        )

    def test_returns_generated_sql(self):
        result = generate_sql(
            "List customers", self.db_path, self.client
        )

        self.assertEqual(result, "SELECT name FROM customers;")

    def test_prompt_contains_question_and_schema(self):
        generate_sql("List customers", self.db_path, self.client)

        messages = (
            self.client.chat.completions.create
            .call_args.kwargs["messages"]
        )

        self.assertIn("List customers", messages[1]["content"])
        self.assertIn("customer_id", messages[1]["content"])

    def test_empty_question_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_sql("   ", self.db_path, self.client)

        self.client.chat.completions.create.assert_not_called()

    def test_missing_database_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            generate_sql(
                "List customers",
                self.db_path.parent / "missing.db",
                self.client
            )

        self.client.chat.completions.create.assert_not_called()


if __name__ == "__main__":
    unittest.main()