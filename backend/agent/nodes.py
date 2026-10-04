"""LangGraph node implementations."""

from __future__ import annotations

import re
from typing import Any, Literal

from langchain_openai import ChatOpenAI
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from backend.agent.browser_registry import close_session, get_or_create_session
from backend.agent.state import AgentState
from backend.browser.portal_actions import (
    find_employee_in_ui,
    grant_application_via_ui,
    open_employee_detail,
    open_portal,
)
from backend.config import OPENAI_API_KEY, OPENAI_MODEL
from backend.db.connection import get_connection
from backend.db import repository as repo
from backend.events.publisher import get_event_publisher
from backend.tools.domain import create_action_plan, find_employee, get_access_policy
from backend.tools.recovery import recover_failed_grant
from backend.tools.verify import verify_final_state


class GoalParse(BaseModel):
    employee_name: str = Field(description="Employee first name or full name")
    role_hint: str | None = Field(
        default=None, description="Role mentioned in the goal if any"
    )


def _llm() -> ChatOpenAI:
    return ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY or None, temperature=0)


def _pub(run_id: str, event_type: str, message: str, **kwargs: Any) -> None:
    get_event_publisher().publish_simple(run_id, event_type, message, **kwargs)


def understand_goal(state: AgentState) -> dict[str, Any]:
    run_id = state["run_id"]
    goal = state["goal"]
    _pub(run_id, "step_started", "Understanding goal", status="running")
    _pub(run_id, "run_started", f"Run started: {goal}", status="running")

    employee_name = None
    role_hint = None

    if OPENAI_API_KEY:
        try:
            structured = _llm().with_structured_output(GoalParse)
            parsed = structured.invoke(
                [
                    {
                        "role": "system",
                        "content": (
                            "Extract the employee name and optional role from an "
                            "IT onboarding goal. Return only structured fields."
                        ),
                    },
                    {"role": "user", "content": goal},
                ]
            )
            employee_name = parsed.employee_name
            role_hint = parsed.role_hint
        except Exception as exc:  # noqa: BLE001
            _pub(run_id, "decision", f"LLM parse fallback: {exc}", status="warning")

    if not employee_name:
        # Deterministic fallback for demo goals
        match = re.search(
            r"[Oo]nboard\s+([A-Za-z]+)",
            goal,
        )
        employee_name = match.group(1) if match else None

    if not employee_name:
        with get_connection() as conn:
            repo.update_run(
                conn, run_id, status="failed", error="Could not identify employee name", completed=True
            )
        return {
            "execution_status": "failed",
            "error": "Could not identify employee name from goal",
        }

    _pub(
        run_id,
        "decision",
        f"Interpreted goal for employee '{employee_name}'"
        + (f" (role hint: {role_hint})" if role_hint else ""),
        status="success",
    )
    return {
        "employee_name": employee_name,
        "execution_status": "running",
        "error": None,
    }


def identify_employee(state: AgentState) -> dict[str, Any]:
    run_id = state["run_id"]
    name = state.get("employee_name") or ""
    _pub(run_id, "step_started", "Identifying employee", status="running")

    employee = find_employee(name)
    if not employee:
        with get_connection() as conn:
            repo.update_run(
                conn,
                run_id,
                status="failed",
                error=f"Employee not found: {name}",
                completed=True,
            )
        return {
            "execution_status": "failed",
            "error": f"Employee not found: {name}",
        }

    with get_connection() as conn:
        repo.update_run(conn, run_id, employee_id=employee["id"])
        repo.write_audit(
            conn,
            action="employee_identified",
            status="succeeded",
            employee_id=employee["id"],
            run_id=run_id,
            details={"name": employee["name"], "role": employee["role_name"]},
        )

    _pub(
        run_id,
        "decision",
        f"Identified {employee['name']} — {employee['role_name']}",
        status="success",
    )
    return {
        "employee_id": employee["id"],
        "employee_name": employee["name"],
        "role_id": employee["role_id"],
        "role_name": employee["role_name"],
    }


def determine_role(state: AgentState) -> dict[str, Any]:
    run_id = state["run_id"]
    _pub(run_id, "step_started", "Determining role", status="running")
    _pub(
        run_id,
        "decision",
        f"Role determined: {state.get('role_name')}",
        status="success",
    )
    with get_connection() as conn:
        repo.write_audit(
            conn,
            action="role_determined",
            status="succeeded",
            employee_id=state.get("employee_id"),
            run_id=run_id,
            details={"role_id": state.get("role_id"), "role_name": state.get("role_name")},
        )
    return {}


def load_access_policy(state: AgentState) -> dict[str, Any]:
    run_id = state["run_id"]
    role_id = state["role_id"]
    _pub(run_id, "step_started", "Loading access policy", status="running")
    policies = get_access_policy(role_id)
    names = [p["application_name"] for p in policies]
    _pub(
        run_id,
        "decision",
        f"Loaded {state.get('role_name')} access policy — apps: {', '.join(names)}",
        status="success",
    )
    with get_connection() as conn:
        repo.write_audit(
            conn,
            action="policy_loaded",
            status="succeeded",
            employee_id=state.get("employee_id"),
            run_id=run_id,
            details={"applications": names},
        )
    return {}


def create_plan(state: AgentState) -> dict[str, Any]:
    run_id = state["run_id"]
    _pub(run_id, "step_started", "Creating action plan", status="running")
    plan = create_action_plan(
        run_id=run_id,
        employee_id=state["employee_id"],
        role_id=state["role_id"],
    )
    for item in plan:
        label = item["application_name"]
        if item["requires_approval"]:
            _pub(
                run_id,
                "decision",
                f"{label} access required (privileged — approval needed)",
                status="warning",
                action_id=item["action_id"],
            )
        else:
            _pub(
                run_id,
                "decision",
                f"{label} access required",
                status="success",
                action_id=item["action_id"],
            )
    return {"action_plan": plan, "browser_started": False}


def _next_pending_action(run_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        actions = repo.list_actions_for_run(conn, run_id)
    for action in actions:
        if action["status"] in {"pending", "failed", "awaiting_approval"}:
            # awaiting_approval is handled by HITL resume path
            if action["status"] == "awaiting_approval":
                return action
            if action["status"] == "failed":
                return action
            if action["status"] == "pending":
                return action
    return None


def execute_actions(state: AgentState) -> dict[str, Any]:
    """Execute remaining actions, pausing at HITL via interrupt()."""
    run_id = state["run_id"]
    employee_id = state["employee_id"]
    session, created = get_or_create_session(run_id)

    # Live registry session is the source of truth for bootstrap. On HITL resume
    # LangGraph restarts this node with browser_started=False, but the page is
    # already open — do not re-run portal/employee navigation.
    if created:
        _pub(run_id, "step_started", "Opening IT administration portal", status="running")
        open_portal(session, run_id)
        find_employee_in_ui(session, employee_id, run_id)
        open_employee_detail(session, employee_id, run_id)
    state_browser = True

    # If resuming from HITL, approval_decision may be set via interrupt resume value
    approval_decision = state.get("approval_decision")

    while True:
        action = _next_pending_action(run_id)
        if action is None:
            return {
                "browser_started": state_browser,
                "current_action_id": None,
                "approval_decision": None,
                "execution_status": "actions_complete",
            }

        action_id = action["id"]
        application_id = action["application_id"]
        app_name = action.get("application_name") or application_id

        # Idempotency: never replay succeeded/skipped
        if action["status"] in {"succeeded", "skipped", "rejected"}:
            continue

        # Privileged HITL — LangGraph restarts this node on resume, so we must
        # call interrupt() again while status is awaiting_approval to receive
        # the Command(resume=...) value. Do not early-return before interrupt().
        if action["requires_approval"] and action["status"] in {
            "pending",
            "awaiting_approval",
        }:
            if action["status"] == "pending":
                with get_connection() as conn:
                    repo.transition_action(conn, action_id, "running")
                    repo.transition_action(conn, action_id, "awaiting_approval")
                    repo.update_run(conn, run_id, status="awaiting_approval")
                    repo.write_audit(
                        conn,
                        action="privileged_access_requested",
                        status="awaiting_approval",
                        employee_id=employee_id,
                        run_id=run_id,
                        details={
                            "application_id": application_id,
                            "application_name": app_name,
                        },
                    )

                _pub(
                    run_id,
                    "approval_required",
                    f"{app_name} requires approval",
                    status="warning",
                    action_id=action_id,
                    details={
                        "application": app_name,
                        "application_id": application_id,
                        "employee": state.get("employee_name"),
                        "reason": f"Required by {state.get('role_name')} access policy",
                        "risk": "Privileged access",
                    },
                )

            decision = interrupt(
                {
                    "type": "approval_required",
                    "action_id": action_id,
                    "application": app_name,
                    "employee": state.get("employee_name"),
                }
            )
            # decision is "approved" or "rejected" from Command(resume=...)
            if isinstance(decision, dict):
                decision = decision.get("decision") or decision.get("value") or decision
            decision_str = str(decision).strip().lower()
            if decision_str not in {"approved", "rejected"}:
                decision_str = "rejected"

            with get_connection() as conn:
                if decision_str == "approved":
                    repo.transition_action(
                        conn,
                        action_id,
                        "running",
                        approval_decision="approved",
                    )
                    repo.update_run(conn, run_id, status="running")
                    repo.write_audit(
                        conn,
                        action="approval_received",
                        status="approved",
                        employee_id=employee_id,
                        run_id=run_id,
                        details={"action_id": action_id, "application": app_name},
                    )
                    _pub(
                        run_id,
                        "approval_received",
                        f"Approval received for {app_name}",
                        status="success",
                        action_id=action_id,
                    )
                    action = repo.get_action(conn, action_id)
                    assert action is not None
                else:
                    repo.transition_action(
                        conn,
                        action_id,
                        "rejected",
                        approval_decision="rejected",
                    )
                    repo.transition_action(conn, action_id, "skipped")
                    repo.update_run(conn, run_id, status="running")
                    repo.write_audit(
                        conn,
                        action="approval_rejected",
                        status="rejected",
                        employee_id=employee_id,
                        run_id=run_id,
                        details={"action_id": action_id, "application": app_name},
                    )
                    _pub(
                        run_id,
                        "approval_received",
                        f"Rejection received — skipping {app_name}",
                        status="warning",
                        action_id=action_id,
                    )
                    continue

        # Failed action → recovery
        if action["status"] == "failed":
            recovery = recover_failed_grant(
                session,
                run_id=run_id,
                action_id=action_id,
                employee_id=employee_id,
                application_id=application_id,
            )
            if not recovery.get("success"):
                with get_connection() as conn:
                    repo.update_run(
                        conn,
                        run_id,
                        status="failed",
                        error=recovery.get("error") or "Recovery failed",
                        completed=True,
                    )
                close_session(run_id)
                return {
                    "execution_status": "failed",
                    "error": recovery.get("error") or "Recovery failed",
                    "browser_started": state_browser,
                    "current_action_id": action_id,
                }
            continue

        # Normal / approved grant via Playwright UI
        if action["status"] in {"pending", "running"}:
            if action["status"] == "pending":
                with get_connection() as conn:
                    repo.transition_action(conn, action_id, "running")

            _pub(
                run_id,
                "action_started",
                f"Granting {app_name}",
                status="running",
                action_id=action_id,
            )

            result = grant_application_via_ui(
                session,
                employee_id=employee_id,
                application_id=application_id,
                run_id=run_id,
                action_id=action_id,
            )

            if result["success"] and result.get("action_completed"):
                with get_connection() as conn:
                    repo.transition_action(conn, action_id, "succeeded")
                _pub(
                    run_id,
                    "action_succeeded",
                    f"Granted {app_name}",
                    status="success",
                    action_id=action_id,
                )
                continue

            # Failure → mark failed then recover immediately
            with get_connection() as conn:
                repo.transition_action(
                    conn,
                    action_id,
                    "failed",
                    error=result.get("error") or "Grant failed",
                )
                repo.write_audit(
                    conn,
                    action="application_grant_failed",
                    status="failed",
                    employee_id=employee_id,
                    run_id=run_id,
                    details={
                        "action_id": action_id,
                        "application": app_name,
                        "error": result.get("error"),
                    },
                )
            _pub(
                run_id,
                "action_failed",
                f"Failed to grant {app_name}: {result.get('error')}",
                status="error",
                action_id=action_id,
            )

            recovery = recover_failed_grant(
                session,
                run_id=run_id,
                action_id=action_id,
                employee_id=employee_id,
                application_id=application_id,
            )
            if not recovery.get("success"):
                with get_connection() as conn:
                    repo.update_run(
                        conn,
                        run_id,
                        status="failed",
                        error=recovery.get("error") or "Recovery failed",
                        completed=True,
                    )
                close_session(run_id)
                return {
                    "execution_status": "failed",
                    "error": recovery.get("error") or "Recovery failed",
                    "browser_started": state_browser,
                    "current_action_id": action_id,
                }
            continue


def verify_and_evidence(state: AgentState) -> dict[str, Any]:
    run_id = state["run_id"]
    if state.get("execution_status") == "failed":
        close_session(run_id)
        _pub(run_id, "run_failed", state.get("error") or "Run failed", status="error")
        return {"execution_status": "failed"}

    session, _created = get_or_create_session(run_id)
    result = verify_final_state(
        session,
        run_id=run_id,
        employee_id=state["employee_id"],
        role_id=state["role_id"],
        goal=state["goal"],
    )
    close_session(run_id)

    if result["passed"]:
        _pub(run_id, "run_completed", "Run completed successfully", status="success")
        return {
            "verification_result": result["verification_result"],
            "execution_status": "complete",
        }

    _pub(run_id, "run_failed", "Verification failed", status="error")
    return {
        "verification_result": result["verification_result"],
        "execution_status": "failed",
        "error": "Verification failed",
    }


def route_after_understand(state: AgentState) -> Literal["identify_employee", "verify_and_evidence"]:
    if state.get("execution_status") == "failed":
        return "verify_and_evidence"
    return "identify_employee"


def route_after_identify(state: AgentState) -> Literal["determine_role", "verify_and_evidence"]:
    if state.get("execution_status") == "failed":
        return "verify_and_evidence"
    return "determine_role"


def route_after_execute(state: AgentState) -> Literal["verify_and_evidence"]:
    return "verify_and_evidence"
