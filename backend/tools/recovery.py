"""State-aware recovery for failed grants."""

from __future__ import annotations

from typing import Any

from backend.browser.portal_actions import grant_application_via_ui, read_permission_from_ui
from backend.browser.session import BrowserSession
from backend.config import MAX_RECOVERY_ATTEMPTS
from backend.db.connection import get_connection
from backend.db import repository as repo
from backend.events.publisher import get_event_publisher
from backend.tools.domain import check_permission


def inspect_states(
    session: BrowserSession,
    *,
    employee_id: str,
    application_id: str,
    run_id: str,
) -> dict[str, Any]:
    ui = read_permission_from_ui(
        session,
        employee_id=employee_id,
        application_id=application_id,
        run_id=run_id,
    )
    db = check_permission(employee_id, application_id)
    browser_granted = ui.get("observed_state") == "permission_granted"
    sqlite_granted = db.get("granted") is True
    return {
        "browser_granted": browser_granted,
        "sqlite_granted": sqlite_granted,
        "ui": ui,
        "db": db,
    }


def recover_failed_grant(
    session: BrowserSession,
    *,
    run_id: str,
    action_id: str,
    employee_id: str,
    application_id: str,
) -> dict[str, Any]:
    """Compare browser vs SQLite before any retry. Never blind-retry."""
    publisher = get_event_publisher()
    publisher.publish_simple(
        run_id,
        "recovery_started",
        f"Recovering action {action_id}",
        status="warning",
        action_id=action_id,
    )

    with get_connection() as conn:
        action = repo.get_action(conn, action_id)
        if not action:
            return {"success": False, "error": "Action not found"}
        if action["recovery_attempts"] >= MAX_RECOVERY_ATTEMPTS:
            repo.write_audit(
                conn,
                action="recovery_exhausted",
                status="failed",
                employee_id=employee_id,
                run_id=run_id,
                details={"action_id": action_id},
            )
            return {
                "success": False,
                "error": "Recovery attempts exhausted",
                "terminal": True,
            }

    states = inspect_states(
        session,
        employee_id=employee_id,
        application_id=application_id,
        run_id=run_id,
    )

    # Browser = granted + SQLite = granted → SUCCESS
    if states["browser_granted"] and states["sqlite_granted"]:
        with get_connection() as conn:
            if action["status"] != "succeeded":
                if action["status"] == "failed":
                    repo.transition_action(conn, action_id, "running")
                repo.transition_action(conn, action_id, "succeeded")
            repo.write_audit(
                conn,
                action="recovery_already_granted",
                status="succeeded",
                employee_id=employee_id,
                run_id=run_id,
                details={"action_id": action_id},
            )
        publisher.publish_simple(
            run_id,
            "recovery_completed",
            "Already granted in browser and SQLite",
            status="success",
            action_id=action_id,
        )
        return {"success": True, "outcome": "already_granted"}

    # Browser != SQLite → FAIL SAFELY
    if states["browser_granted"] != states["sqlite_granted"]:
        with get_connection() as conn:
            repo.write_audit(
                conn,
                action="recovery_inconsistent_state",
                status="failed",
                employee_id=employee_id,
                run_id=run_id,
                details={
                    "action_id": action_id,
                    "browser_granted": states["browser_granted"],
                    "sqlite_granted": states["sqlite_granted"],
                },
            )
        publisher.publish_simple(
            run_id,
            "recovery_completed",
            "Inconsistent browser/SQLite state — failing safely",
            status="error",
            action_id=action_id,
        )
        return {
            "success": False,
            "error": "Inconsistent browser/SQLite state",
            "terminal": True,
            "outcome": "inconsistent",
        }

    # Both unchanged → SAFE RETRY
    with get_connection() as conn:
        repo.transition_action(
            conn, action_id, "running", increment_recovery=True
        )
        repo.write_audit(
            conn,
            action="recovery_retry",
            status="running",
            employee_id=employee_id,
            run_id=run_id,
            details={"action_id": action_id},
        )

    result = grant_application_via_ui(
        session,
        employee_id=employee_id,
        application_id=application_id,
        run_id=run_id,
        action_id=f"{action_id}_recovery",
    )

    with get_connection() as conn:
        if result["success"] and result.get("action_completed"):
            repo.transition_action(conn, action_id, "succeeded")
            repo.write_audit(
                conn,
                action="recovery_succeeded",
                status="succeeded",
                employee_id=employee_id,
                run_id=run_id,
                details={"action_id": action_id},
            )
            publisher.publish_simple(
                run_id,
                "recovery_completed",
                "Safe retry succeeded",
                status="success",
                action_id=action_id,
            )
            return {"success": True, "outcome": "retried", "browser": result}

        repo.transition_action(
            conn,
            action_id,
            "failed",
            error=result.get("error") or "Recovery retry failed",
        )
        repo.write_audit(
            conn,
            action="recovery_failed",
            status="failed",
            employee_id=employee_id,
            run_id=run_id,
            details={"action_id": action_id, "error": result.get("error")},
        )

    publisher.publish_simple(
        run_id,
        "recovery_completed",
        "Safe retry failed",
        status="error",
        action_id=action_id,
    )
    return {
        "success": False,
        "error": result.get("error") or "Recovery retry failed",
        "terminal": True,
        "outcome": "retry_failed",
        "browser": result,
    }
