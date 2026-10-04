"""Deterministic domain tools (SQLite reads / action planning)."""

from __future__ import annotations

from typing import Any

from backend.db.connection import get_connection
from backend.db import repository as repo


def find_employee(name: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        return repo.find_employee_by_name(conn, name)


def get_role(role_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        for role in repo.list_roles(conn):
            if role["id"] == role_id:
                return role
    return None


def get_access_policy(role_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        return repo.get_policies_for_role(conn, role_id)


def create_action_plan(
    *,
    run_id: str,
    employee_id: str,
    role_id: str,
) -> list[dict[str, Any]]:
    with get_connection() as conn:
        policies = repo.get_policies_for_role(conn, role_id)
        plan: list[dict[str, Any]] = []
        for index, policy in enumerate(policies, start=1):
            # Include run_id so action IDs remain unique across runs.
            action_id = f"act_{index:03d}_{run_id[-10:]}"
            requires_approval = bool(policy["privileged"])
            repo.create_action(
                conn,
                action_id=action_id,
                run_id=run_id,
                employee_id=employee_id,
                application_id=policy["application_id"],
                action_type="grant_application",
                requires_approval=requires_approval,
                details={
                    "application_name": policy["application_name"],
                    "privileged": requires_approval,
                },
            )
            plan.append(
                {
                    "action_id": action_id,
                    "employee_id": employee_id,
                    "application_id": policy["application_id"],
                    "application_name": policy["application_name"],
                    "action_type": "grant_application",
                    "requires_approval": requires_approval,
                    "status": "pending",
                }
            )
        repo.write_audit(
            conn,
            action="action_plan_created",
            status="succeeded",
            employee_id=employee_id,
            run_id=run_id,
            details={"action_count": len(plan)},
        )
        return plan


def check_permission(employee_id: str, application_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        perm = repo.get_permission(conn, employee_id, application_id)
        if perm and perm["status"] == "granted":
            return {"granted": True, "status": "granted"}
        return {"granted": False, "status": perm["status"] if perm else "absent"}
