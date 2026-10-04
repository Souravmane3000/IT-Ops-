"""LangGraph workflow state (execution context only)."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class AgentState(TypedDict, total=False):
    run_id: str
    goal: str
    employee_id: str | None
    employee_name: str | None
    role_id: str | None
    role_name: str | None
    action_plan: list[dict[str, Any]]
    current_action_id: str | None
    approval_decision: Literal["approved", "rejected"] | None
    verification_result: dict[str, Any] | None
    execution_status: str
    error: str | None
    browser_started: bool
