import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import ValidationError

from app import initialize_db
from llm_sql import generate_sql, generate_structured_sql


class LlmSqlTests(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        self.db_path = Path(temp_dir.name) / "test.db"
        initialize_db(self.db_path)

        self.client = Mock()

        self.set_response({
            "sql": "SELECT name FROM customers;",
            "explanation": "Lists all customers."
        })

    def set_response(self, payload):
        content = (
            json.dumps(payload)
            if isinstance(payload, dict)
            else payload
        )

        self.client.chat.completions.create.return_value = (
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=content)
                    )
                ]
            )
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

    def test_returns_structured_response(self):
        result = generate_structured_sql(
            "List customers", self.db_path, self.client
        )

        self.assertEqual(result.sql, "SELECT name FROM customers;")
        self.assertEqual(result.explanation, "Lists all customers.")

    def test_requests_strict_json_schema(self):
        generate_structured_sql(
            "List customers", self.db_path, self.client
        )

        response_format = (
            self.client.chat.completions.create
            .call_args.kwargs["response_format"]
        )

        self.assertEqual(response_format["type"], "json_schema")
        self.assertTrue(response_format["json_schema"]["strict"])

        schema = response_format["json_schema"]["schema"]
        self.assertEqual(set(schema["required"]), {"sql", "explanation"})
        self.assertFalse(schema["additionalProperties"])

    def test_missing_field_is_rejected(self):
        self.set_response({"sql": "SELECT name FROM customers;"})

        with self.assertRaises(ValidationError):
            generate_structured_sql(
                "List customers", self.db_path, self.client
            )

    def test_empty_sql_is_rejected(self):
        self.set_response({
            "sql": "   ",
            "explanation": "No SQL generated."
        })

        with self.assertRaises(ValidationError):
            generate_structured_sql(
                "List customers", self.db_path, self.client
            )

    def test_invalid_json_is_rejected(self):
        self.set_response("not valid json")

        with self.assertRaises(ValidationError):
            generate_structured_sql(
                "List customers", self.db_path, self.client
            )


if __name__ == "__main__":
    unittest.main()