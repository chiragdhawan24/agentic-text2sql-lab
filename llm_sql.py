import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from app import DB_PATH
from schema_tool import inspect_database_schema


def generate_sql(question: str, db_path: Path = DB_PATH, client=None) -> str:
    if not question.strip():
        raise ValueError("Question cannot be empty")

    # Step 2: Retrieve the actual database schema
    schema = inspect_database_schema(db_path)

    load_dotenv()

    # Create an LLM client unless a test client was supplied
    if client is None:
        if not os.getenv("GROQ_API_KEY"):
            raise RuntimeError("Add GROQ_API_KEY to your .env file")

        from groq import Groq
        client = Groq()

    # Send schema + question to the LLM
    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        messages=[
            {
                "role": "system",
                "content": (
                    "Translate the user's question into one SQLite SELECT query. "
                    "Use only the supplied database schema. "
                    "Return SQL only, without markdown or explanation. "
                    "Never generate statements that modify data or schema."
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
    )

    sql = (response.choices[0].message.content or "").strip()

    if not sql:
        raise ValueError("The model returned an empty response")

    return sql


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Which customer placed the most orders?"
    print(generate_sql(question))