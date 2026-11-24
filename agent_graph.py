import json
import sys
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import StateGraph, START, END

from app import DB_PATH
from schema_tool import inspect_database_schema
from llm_sql import generate_structured_sql
from sql_tool import execute_read_only_sql


# Shared state passed between LangGraph nodes
class AgentState(TypedDict, total=False):
    question: str
    db_path: Path
    schema: dict[str, Any]
    sql: str
    explanation: str
    result: dict[str, Any]


# Node 1: Inspect database schema
def inspect_schema_node(state: AgentState) -> dict:
    question = state.get("question")

    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question cannot be empty")

    schema = inspect_database_schema(
        state.get("db_path", DB_PATH)
    )

    return {"schema": schema}


# Node 2: Generate SQL using the LLM
def generate_sql_node(state: AgentState) -> dict:
    generation = generate_structured_sql(
        question=state["question"],
        db_path=state.get("db_path", DB_PATH),
        schema=state["schema"],
    )

    return {
        "sql": generation.sql,
        "explanation": generation.explanation,
    }


# Node 3: Execute SQL safely
def execute_sql_node(state: AgentState) -> dict:
    result = execute_read_only_sql(
        state["sql"],
        db_path=state.get("db_path", DB_PATH),
    )

    return {"result": result}


# Assemble and compile the graph
def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("inspect_schema", inspect_schema_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("execute_sql", execute_sql_node)

    workflow.add_edge(START, "inspect_schema")
    workflow.add_edge("inspect_schema", "generate_sql")
    workflow.add_edge("generate_sql", "execute_sql")
    workflow.add_edge("execute_sql", END)

    return workflow.compile()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(
            'Usage: python agent_graph.py "Your question"'
        )

    question = " ".join(sys.argv[1:])

    graph = build_graph()
    state = graph.invoke({"question": question})

    print(json.dumps({
        "question": state["question"],
        "sql": state["sql"],
        "explanation": state["explanation"],
        "result": state["result"],
    }, indent=2))