import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import initialize_db
from agent_graph import build_graph
from llm_sql import SqlGeneration


class AgentGraphTests(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        self.db_path = Path(temp_dir.name) / "test.db"
        initialize_db(self.db_path)

    def test_graph_executes_query(self):
        generated = SqlGeneration(
            sql=(
                "SELECT SUM(quantity * unit_price) AS revenue "
                "FROM order_items"
            ),
            explanation="Calculates total revenue.",
        )

        with patch(
            "agent_graph.generate_structured_sql",
            return_value=generated,
        ) as mock_generator:
            state = build_graph().invoke({
                "question": "What is the total revenue?",
                "db_path": self.db_path,
            })

        self.assertEqual(state["result"]["rows"], [[320.0]])
        self.assertEqual(
            state["explanation"],
            "Calculates total revenue.",
        )

        # Verify that schema inspection reached the LLM node
        schema = mock_generator.call_args.kwargs["schema"]
        self.assertIn("order_items", schema)

    def test_unsafe_sql_is_rejected(self):
        generated = SqlGeneration(
            sql="DELETE FROM customers",
            explanation="Unsafe operation.",
        )

        with patch(
            "agent_graph.generate_structured_sql",
            return_value=generated,
        ):
            with self.assertRaises(ValueError):
                build_graph().invoke({
                    "question": "Delete all customers",
                    "db_path": self.db_path,
                })

        # Confirm no records were deleted
        with sqlite3.connect(self.db_path) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM customers"
            ).fetchone()[0]

        self.assertEqual(count, 2)

    def test_missing_database_is_rejected(self):
        with patch(
            "agent_graph.generate_structured_sql"
        ) as mock_generator:
            with self.assertRaises(FileNotFoundError):
                build_graph().invoke({
                    "question": "List customers",
                    "db_path": self.db_path.parent / "missing.db",
                })

            mock_generator.assert_not_called()

    def test_empty_question_is_rejected(self):
        with patch(
            "agent_graph.generate_structured_sql"
        ) as mock_generator:
            with self.assertRaises(ValueError):
                build_graph().invoke({
                    "question": "   ",
                    "db_path": self.db_path,
                })

            mock_generator.assert_not_called()


if __name__ == "__main__":
    unittest.main()