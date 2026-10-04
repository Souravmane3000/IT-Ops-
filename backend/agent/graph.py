"""Single LangGraph workflow with persistent SQLite checkpointer."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from backend.agent.nodes import (
    create_plan,
    determine_role,
    execute_actions,
    identify_employee,
    load_access_policy,
    route_after_identify,
    route_after_understand,
    understand_goal,
    verify_and_evidence,
)
from backend.agent.state import AgentState
import backend.config as config


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("understand_goal", understand_goal)
    graph.add_node("identify_employee", identify_employee)
    graph.add_node("determine_role", determine_role)
    graph.add_node("load_access_policy", load_access_policy)
    graph.add_node("create_plan", create_plan)
    graph.add_node("execute_actions", execute_actions)
    graph.add_node("verify_and_evidence", verify_and_evidence)

    graph.add_edge(START, "understand_goal")
    graph.add_conditional_edges("understand_goal", route_after_understand)
    graph.add_conditional_edges("identify_employee", route_after_identify)
    graph.add_edge("determine_role", "load_access_policy")
    graph.add_edge("load_access_policy", "create_plan")
    graph.add_edge("create_plan", "execute_actions")
    graph.add_edge("execute_actions", "verify_and_evidence")
    graph.add_edge("verify_and_evidence", END)
    return graph


@lru_cache(maxsize=1)
def get_compiled_graph():
    checkpoint_path = config.CHECKPOINT_DB_PATH
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3

    conn = sqlite3.connect(str(checkpoint_path), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()
    return build_graph().compile(checkpointer=checkpointer)


def run_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


def start_run(run_id: str, goal: str) -> Any:
    graph = get_compiled_graph()
    initial: AgentState = {
        "run_id": run_id,
        "goal": goal,
        "employee_id": None,
        "employee_name": None,
        "role_id": None,
        "role_name": None,
        "action_plan": [],
        "current_action_id": None,
        "approval_decision": None,
        "verification_result": None,
        "execution_status": "running",
        "error": None,
        "browser_started": False,
    }
    return graph.invoke(initial, config=run_config(run_id))


def resume_run(run_id: str, decision: str) -> Any:
    graph = get_compiled_graph()
    return graph.invoke(Command(resume=decision), config=run_config(run_id))
