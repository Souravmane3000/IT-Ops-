"""Domain repository — authoritative reads/writes for it_ops.db."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def list_roles(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT id, name FROM roles ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def list_employees(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT e.id, e.name, e.role_id, r.name AS role_name
        FROM employees e
        JOIN roles r ON r.id = e.role_id
        ORDER BY e.name
        """
    ).fetchall()
    return [dict(r) for r in rows]


def get_employee(conn: sqlite3.Connection, employee_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT e.id, e.name, e.role_id, r.name AS role_name
        FROM employees e
        JOIN roles r ON r.id = e.role_id
        WHERE e.id = ?
        """,
        (employee_id,),
    ).fetchone()
    return dict(row) if row else None


def find_employee_by_name(conn: sqlite3.Connection, name: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT e.id, e.name, e.role_id, r.name AS role_name
        FROM employees e
        JOIN roles r ON r.id = e.role_id
        WHERE LOWER(e.name) = LOWER(?)
        """,
        (name.strip(),),
    ).fetchone()
    return dict(row) if row else None


def list_applications(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, name, privileged, fails_on_grant, fail_remaining
        FROM applications
        ORDER BY name
        """
    ).fetchall()
    return [
        {
            **dict(r),
            "privileged": bool(r["privileged"]),
            "fails_on_grant": bool(r["fails_on_grant"]),
        }
        for r in rows
    ]


def get_application(conn: sqlite3.Connection, application_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, name, privileged, fails_on_grant, fail_remaining
        FROM applications WHERE id = ?
        """,
        (application_id,),
    ).fetchone()
    if not row:
        return None
    return {
        **dict(row),
        "privileged": bool(row["privileged"]),
        "fails_on_grant": bool(row["fails_on_grant"]),
    }


def list_policies(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT p.id, p.role_id, r.name AS role_name,
               p.application_id, a.name AS application_name,
               p.required, a.privileged
        FROM access_policies p
        JOIN roles r ON r.id = p.role_id
        JOIN applications a ON a.id = p.application_id
        ORDER BY r.name, a.name
        """
    ).fetchall()
    return [
        {
            **dict(r),
            "required": bool(r["required"]),
            "privileged": bool(r["privileged"]),
        }
        for r in rows
    ]


def get_policies_for_role(conn: sqlite3.Connection, role_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT p.id, p.role_id, p.application_id, p.required,
               a.name AS application_name, a.privileged, a.fails_on_grant
        FROM access_policies p
        JOIN applications a ON a.id = p.application_id
        WHERE p.role_id = ? AND p.required = 1
        ORDER BY a.privileged ASC, a.name
        """,
        (role_id,),
    ).fetchall()
    return [
        {
            **dict(r),
            "required": bool(r["required"]),
            "privileged": bool(r["privileged"]),
            "fails_on_grant": bool(r["fails_on_grant"]),
        }
        for r in rows
    ]


def get_permission(
    conn: sqlite3.Connection, employee_id: str, application_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT id, employee_id, application_id, status
        FROM permissions
        WHERE employee_id = ? AND application_id = ?
        """,
        (employee_id, application_id),
    ).fetchone()
    return dict(row) if row else None


def list_permissions_for_employee(
    conn: sqlite3.Connection, employee_id: str
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT p.id, p.employee_id, p.application_id, p.status,
               a.name AS application_name, a.privileged
        FROM permissions p
        JOIN applications a ON a.id = p.application_id
        WHERE p.employee_id = ?
        ORDER BY a.name
        """,
        (employee_id,),
    ).fetchall()
    return [{**dict(r), "privileged": bool(r["privileged"])} for r in rows]


def list_audit(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, run_id, employee_id, action, status, timestamp, details
        FROM audit_log
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Mutations — portal grant (authoritative permission writes)
# ---------------------------------------------------------------------------


def grant_application(
    conn: sqlite3.Connection,
    employee_id: str,
    application_id: str,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Authoritative grant used by the portal API only."""
    employee = get_employee(conn, employee_id)
    if not employee:
        return {"success": False, "error": "Employee not found"}

    application = get_application(conn, application_id)
    if not application:
        return {"success": False, "error": "Application not found"}

    existing = get_permission(conn, employee_id, application_id)
    if existing and existing["status"] == "granted":
        return {
            "success": True,
            "employee_id": employee_id,
            "application_id": application_id,
            "status": "granted",
            "already_granted": True,
        }

    # Controlled failure injection (one-shot via fail_remaining)
    if application["fails_on_grant"] and application["fail_remaining"] > 0:
        conn.execute(
            "UPDATE applications SET fail_remaining = fail_remaining - 1 WHERE id = ?",
            (application_id,),
        )
        write_audit(
            conn,
            action="application_grant_failed",
            status="failed",
            employee_id=employee_id,
            run_id=run_id,
            details={
                "application_id": application_id,
                "application_name": application["name"],
                "reason": "controlled_failure_injection",
            },
        )
        return {
            "success": False,
            "employee_id": employee_id,
            "application_id": application_id,
            "status": "failed",
            "error": f"Controlled failure: failed to grant {application['name']}",
        }

    if existing:
        conn.execute(
            "UPDATE permissions SET status = 'granted' WHERE id = ?",
            (existing["id"],),
        )
        perm_id = existing["id"]
    else:
        perm_id = new_id("perm")
        conn.execute(
            """
            INSERT INTO permissions (id, employee_id, application_id, status)
            VALUES (?, ?, ?, 'granted')
            """,
            (perm_id, employee_id, application_id),
        )

    write_audit(
        conn,
        action="application_granted",
        status="succeeded",
        employee_id=employee_id,
        run_id=run_id,
        details={
            "application_id": application_id,
            "application_name": application["name"],
            "permission_id": perm_id,
        },
    )
    return {
        "success": True,
        "employee_id": employee_id,
        "application_id": application_id,
        "status": "granted",
        "already_granted": False,
    }


def write_audit(
    conn: sqlite3.Connection,
    *,
    action: str,
    status: str,
    employee_id: str | None = None,
    run_id: str | None = None,
    details: dict[str, Any] | str | None = None,
) -> str:
    audit_id = new_id("aud")
    details_str = (
        json.dumps(details) if isinstance(details, dict) else (details or None)
    )
    conn.execute(
        """
        INSERT INTO audit_log (id, run_id, employee_id, action, status, timestamp, details)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (audit_id, run_id, employee_id, action, status, utc_now(), details_str),
    )
    return audit_id


# ---------------------------------------------------------------------------
# Runs / actions
# ---------------------------------------------------------------------------


VALID_ACTION_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running"},
    "running": {"succeeded", "failed", "awaiting_approval"},
    "awaiting_approval": {"running", "rejected"},
    "rejected": {"skipped"},
    "failed": {"running"},  # recovery retry
    "succeeded": set(),
    "skipped": set(),
}


def create_run(conn: sqlite3.Connection, run_id: str, goal: str) -> dict[str, Any]:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO runs (id, goal, status, employee_id, created_at, updated_at, completed_at, error)
        VALUES (?, ?, 'running', NULL, ?, ?, NULL, NULL)
        """,
        (run_id, goal, now, now),
    )
    return get_run(conn, run_id)  # type: ignore[return-value]


def get_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def update_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    status: str | None = None,
    employee_id: str | None = None,
    error: str | None = None,
    completed: bool = False,
) -> None:
    run = get_run(conn, run_id)
    if not run:
        return
    new_status = status if status is not None else run["status"]
    new_employee = employee_id if employee_id is not None else run["employee_id"]
    new_error = error if error is not None else run["error"]
    completed_at = utc_now() if completed else run["completed_at"]
    conn.execute(
        """
        UPDATE runs
        SET status = ?, employee_id = ?, error = ?, updated_at = ?, completed_at = ?
        WHERE id = ?
        """,
        (new_status, new_employee, new_error, utc_now(), completed_at, run_id),
    )


def create_action(
    conn: sqlite3.Connection,
    *,
    action_id: str,
    run_id: str,
    employee_id: str,
    application_id: str,
    action_type: str = "grant_application",
    requires_approval: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conn.execute(
        """
        INSERT INTO actions (
            id, run_id, employee_id, application_id, action_type, status,
            requires_approval, approval_decision, recovery_attempts, error,
            started_at, completed_at, details
        ) VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL, 0, NULL, NULL, NULL, ?)
        """,
        (
            action_id,
            run_id,
            employee_id,
            application_id,
            action_type,
            1 if requires_approval else 0,
            json.dumps(details or {}),
        ),
    )
    return get_action(conn, action_id)  # type: ignore[return-value]


def get_action(conn: sqlite3.Connection, action_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["requires_approval"] = bool(data["requires_approval"])
    return data


def list_actions_for_run(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT a.*, app.name AS application_name, app.privileged
        FROM actions a
        JOIN applications app ON app.id = a.application_id
        WHERE a.run_id = ?
        ORDER BY a.id
        """,
        (run_id,),
    ).fetchall()
    result = []
    for r in rows:
        data = dict(r)
        data["requires_approval"] = bool(data["requires_approval"])
        data["privileged"] = bool(data["privileged"])
        result.append(data)
    return result


def transition_action(
    conn: sqlite3.Connection,
    action_id: str,
    new_status: str,
    *,
    error: str | None = None,
    approval_decision: str | None = None,
    increment_recovery: bool = False,
    details_update: dict[str, Any] | None = None,
) -> dict[str, Any]:
    action = get_action(conn, action_id)
    if not action:
        raise ValueError(f"Action not found: {action_id}")

    current = action["status"]
    allowed = VALID_ACTION_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise ValueError(f"Invalid transition {current} → {new_status}")

    started_at = action["started_at"] or utc_now()
    completed_at = action["completed_at"]
    if new_status in {"succeeded", "failed", "skipped", "rejected", "awaiting_approval"}:
        if new_status in {"succeeded", "failed", "skipped"}:
            completed_at = utc_now()

    recovery = action["recovery_attempts"]
    if increment_recovery:
        recovery += 1

    details = action.get("details")
    if details_update:
        try:
            parsed = json.loads(details) if details else {}
        except json.JSONDecodeError:
            parsed = {}
        parsed.update(details_update)
        details = json.dumps(parsed)

    conn.execute(
        """
        UPDATE actions
        SET status = ?, error = ?, approval_decision = COALESCE(?, approval_decision),
            recovery_attempts = ?, started_at = ?, completed_at = ?, details = ?
        WHERE id = ?
        """,
        (
            new_status,
            error if error is not None else action["error"],
            approval_decision,
            recovery,
            started_at,
            completed_at,
            details,
            action_id,
        ),
    )
    return get_action(conn, action_id)  # type: ignore[return-value]
