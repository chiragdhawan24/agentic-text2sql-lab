import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, field_validator

from app import DB_PATH
from schema_tool import inspect_database_schema


# Define the expected LLM output structure
class SqlGeneration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sql: str
    explanation: str

    @field_validator("sql")
    @classmethod
    def reject_empty_sql(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Generated SQL cannot be empty")
        return value.strip()


def generate_structured_sql(
    question: str,
    db_path: Path = DB_PATH,
    client=None,
    schema: dict | None = None
) -> SqlGeneration:

    if not question.strip():
        raise ValueError("Question cannot be empty")

    # Retrieve the real database schema if it is not provided
    if schema is None:
        schema = inspect_database_schema(db_path)

    load_dotenv()

    if client is None:
        if not os.getenv("GROQ_API_KEY"):
            raise RuntimeError("Add GROQ_API_KEY to your .env file")

        from groq import Groq
        client = Groq()

    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a Text-to-SQL assistant. "
                    "Generate one SQLite SELECT query using only "
                    "the supplied database schema. "
                    "Return SQL and a brief explanation. "
                    "Never generate data-modifying statements. "
                    "Do not include markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Database schema:\n{json.dumps(schema, indent=2)}\n\n"
                    f"Question:\n{question}"
                ),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "sql_generation",
                "strict": True,
                "schema": SqlGeneration.model_json_schema(),
            },
        },
    )

    content = response.choices[0].message.content

    if not content:
        raise ValueError("The model returned an empty response")

    # Validate the response against our Pydantic model
    return SqlGeneration.model_validate_json(content)


# Preserve the Step 3 interface
def generate_sql(
    question: str,
    db_path: Path = DB_PATH,
    client=None
) -> str:
    return generate_structured_sql(
        question, db_path, client
    ).sql


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "What is the total revenue?"

    result = generate_structured_sql(question)
    print(result.model_dump_json(indent=2))