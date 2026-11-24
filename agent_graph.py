import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import StateGraph, START, END

from app import DB_PATH
from schema_tool import inspect_database_schema
from llm_sql import generate_structured_sql
from sql_tool import execute_read_only_sql


# Initial execution + maximum 2 repair attempts
MAX_ATTEMPTS = 3

# Only query-construction errors should trigger repair.
REPAIRABLE_ERRORS = (
    "no such table:",
    "no such column:",
    "ambiguous column name:",
    "no such function:",
    "near ",
    "incomplete input",
    "unrecognized token:",
    "misuse of aggregate",
    "wrong number of arguments to function",
)


class AgentState(TypedDict, total=False):
    question: str
    db_path: Path
    schema: dict[str, Any]
    sql: str
    explanation: str
    result: dict[str, Any] | None
    error: str | None
    attempts: int


# Node 1: Inspect database schema
def inspect_schema_node(state: AgentState) -> dict:
    question = state.get("question")

    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question cannot be empty")

    schema = inspect_database_schema(
        state.get("db_path", DB_PATH)
    )

    return {"schema": schema}


# Node 2: Generate initial SQL
def generate_sql_node(state: AgentState) -> dict:
    generation = generate_structured_sql(
        question=state["question"],
        db_path=state.get("db_path", DB_PATH),
        schema=state["schema"],
    )

    return {
        "sql": generation.sql,
        "explanation": generation.explanation,
        "attempts": 0,
        "error": None,
    }


# Node 3: Execute SQL and capture repairable errors
def execute_sql_node(state: AgentState) -> dict:
    attempts = state.get("attempts", 0) + 1

    try:
        result = execute_read_only_sql(
            state["sql"],
            db_path=state.get("db_path", DB_PATH),
        )

    except sqlite3.OperationalError as exc:
        error = str(exc)

        # Never retry authorization, timeout, or other
        # non-repairable database errors.
        if not error.lower().startswith(REPAIRABLE_ERRORS):
            raise

        return {
            "result": None,
            "error": error,
            "attempts": attempts,
        }

    return {
        "result": result,
        "error": None,
        "attempts": attempts,
    }


# Conditional routing: finish or retry?
def route_after_execution(state: AgentState) -> str:
    if state.get("error") and state["attempts"] < MAX_ATTEMPTS:
        return "repair"

    return "end"


# Node 4: Ask the LLM to repair failed SQL
def repair_sql_node(state: AgentState) -> dict:
    repair_prompt = (
        f"Original question:\n{state['question']}\n\n"
        f"Previous SQL:\n{state['sql']}\n\n"
        f"SQLite error:\n{state['error']}\n\n"
        "Correct the SQL using the supplied database schema. "
        "Return one valid SQLite SELECT query and a brief explanation."
    )

    generation = generate_structured_sql(
        question=repair_prompt,
        db_path=state.get("db_path", DB_PATH),
        schema=state["schema"],
    )

    return {
        "sql": generation.sql,
        "explanation": generation.explanation,
    }


# Assemble the graph
def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("inspect_schema", inspect_schema_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("execute_sql", execute_sql_node)
    workflow.add_node("repair_sql", repair_sql_node)

    workflow.add_edge(START, "inspect_schema")
    workflow.add_edge("inspect_schema", "generate_sql")
    workflow.add_edge("generate_sql", "execute_sql")

    # Conditional edge after execution
    workflow.add_conditional_edges(
        "execute_sql",
        route_after_execution,
        {
            "repair": "repair_sql",
            "end": END,
        },
    )

    # Feedback loop: repair -> re-execute
    workflow.add_edge("repair_sql", "execute_sql")

    return workflow.compile()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(
            'Usage: python agent_graph.py "Your question"'
        )

    question = " ".join(sys.argv[1:])

    state = build_graph().invoke({"question": question})

    print(json.dumps({
        "question": state["question"],
        "sql": state["sql"],
        "explanation": state["explanation"],
        "attempts": state["attempts"],
        "error": state.get("error"),
        "result": state.get("result"),
    }, indent=2))

    if state.get("error"):
        sys.exit(1)