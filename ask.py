import json
import sys

from llm_sql import generate_structured_sql
from sql_tool import execute_read_only_sql


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python ask.py "Your question"')

    question = " ".join(sys.argv[1:])

    # Step 4: Generate structured SQL using the LLM.
    generation = generate_structured_sql(question)

    # Step 5: Execute SQL using our read-only tool.
    result = execute_read_only_sql(generation.sql)

    print(json.dumps({
        "question": question,
        "sql": generation.sql,
        "explanation": generation.explanation,
        "result": result,
    }, indent=2))


if __name__ == "__main__":
    main()