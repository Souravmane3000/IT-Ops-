"""Independent verification after execution."""

from __future__ import annotations

from typing import Any

from backend.browser.portal_actions import capture_verification_screenshot
from backend.browser.session import BrowserSession
from backend.db.connection import get_connection
from backend.db import repository as repo
from backend.evidence.writer import list_evidence_files, write_result_json
from backend.events.publisher import get_event_publisher


def verify_final_state(
    session: BrowserSession,
    *,
    run_id: str,
    employee_id: str,
    role_id: str,
    goal: str,
) -> dict[str, Any]:
    publisher = get_event_publisher()
    publisher.publish_simple(
        run_id, "verification_started", "Starting independent verification"
    )

    checks: list[dict[str, Any]] = []
    passed = True

    with get_connection() as conn:
        employee = repo.get_employee(conn, employee_id)
        if not employee:
            checks.append({"check": "employee_exists", "pass": False})
            passed = False
        else:
            checks.append(
                {
                    "check": "employee_exists",
                    "pass": True,
                    "employee": employee["name"],
                }
            )
            role_ok = employee["role_id"] == role_id
            checks.append(
                {
                    "check": "correct_role",
                    "pass": role_ok,
                    "expected": role_id,
                    "actual": employee["role_id"],
                }
            )
            if not role_ok:
                passed = False

        actions = repo.list_actions_for_run(conn, run_id)
        policies = repo.get_policies_for_role(conn, role_id)
        required_app_ids = {p["application_id"] for p in policies}

        for action in actions:
            app_id = action["application_id"]
            perm = repo.get_permission(conn, employee_id, app_id)
            granted = bool(perm and perm["status"] == "granted")

            if action["status"] == "skipped" or action["status"] == "rejected":
                # Privileged rejection: must NOT be granted
                ok = not granted
                checks.append(
                    {
                        "check": f"skipped_not_granted:{app_id}",
                        "pass": ok,
                        "action_status": action["status"],
                    }
                )
                if not ok:
                    passed = False
                continue

            if action["requires_approval"]:
                decision = action.get("approval_decision")
                if decision == "approved":
                    ok = granted and action["status"] == "succeeded"
                    checks.append(
                        {
                            "check": f"privileged_approved_granted:{app_id}",
                            "pass": ok,
                        }
                    )
                    if not ok:
                        passed = False
                elif decision == "rejected":
                    ok = not granted
                    checks.append(
                        {
                            "check": f"privileged_rejected_not_granted:{app_id}",
                            "pass": ok,
                        }
                    )
                    if not ok:
                        passed = False
                else:
                    checks.append(
                        {
                            "check": f"privileged_decision_present:{app_id}",
                            "pass": False,
                        }
                    )
                    passed = False
                continue

            # Non-privileged required apps must be granted/succeeded
            if app_id in required_app_ids:
                ok = granted and action["status"] == "succeeded"
                checks.append(
                    {
                        "check": f"required_granted:{app_id}",
                        "pass": ok,
                        "action_status": action["status"],
                        "granted": granted,
                        "recovery_attempts": action["recovery_attempts"],
                    }
                )
                if not ok:
                    passed = False

        audit_rows = [
            a for a in repo.list_audit(conn, limit=500) if a.get("run_id") == run_id
        ]
        audit_ok = len(audit_rows) > 0
        checks.append({"check": "audit_records_exist", "pass": audit_ok, "count": len(audit_rows)})
        if not audit_ok:
            passed = False

        permissions = repo.list_permissions_for_employee(conn, employee_id)
        granted_perms = [p for p in permissions if p["status"] == "granted"]

    # Evidence / screenshot
    shot = capture_verification_screenshot(session, employee_id, run_id)
    evidence_files = list_evidence_files(run_id)
    evidence_ok = len(evidence_files) > 0 and shot.get("success")
    checks.append(
        {
            "check": "evidence_available",
            "pass": bool(evidence_ok),
            "file_count": len(evidence_files),
        }
    )
    if not evidence_ok:
        passed = False

    verification_result = {
        "passed": passed,
        "checks": checks,
    }

    with get_connection() as conn:
        employee = repo.get_employee(conn, employee_id)
        actions = repo.list_actions_for_run(conn, run_id)
        permissions = [
            p
            for p in repo.list_permissions_for_employee(conn, employee_id)
            if p["status"] == "granted"
        ]
        audit_rows = [
            a for a in repo.list_audit(conn, limit=500) if a.get("run_id") == run_id
        ]

        result_payload = {
            "run_id": run_id,
            "goal": goal,
            "status": "complete" if passed else "failed",
            "employee": {
                "id": employee_id,
                "name": employee["name"] if employee else None,
                "role": employee["role_name"] if employee else None,
            },
            "actions_performed": [
                {
                    "action_id": a["id"],
                    "application_id": a["application_id"],
                    "application_name": a.get("application_name"),
                    "status": a["status"],
                    "requires_approval": a["requires_approval"],
                    "approval_decision": a.get("approval_decision"),
                    "recovery_attempts": a["recovery_attempts"],
                }
                for a in actions
            ],
            "permissions_granted": [
                {
                    "application_id": p["application_id"],
                    "application_name": p["application_name"],
                }
                for p in permissions
            ],
            "verification_result": verification_result,
            "audit_count": len(audit_rows),
            "timestamp": repo.utc_now(),
        }
        write_result_json(run_id, result_payload)

        final_status = "complete" if passed else "failed"
        repo.update_run(
            conn,
            run_id,
            status=final_status,
            error=None if passed else "Verification failed",
            completed=True,
        )
        repo.write_audit(
            conn,
            action="verification_completed",
            status="succeeded" if passed else "failed",
            employee_id=employee_id,
            run_id=run_id,
            details=verification_result,
        )

    publisher.publish_simple(
        run_id,
        "verification_completed",
        "Verification passed" if passed else "Verification failed",
        status="success" if passed else "error",
        details=verification_result,
    )
    return {
        "passed": passed,
        "verification_result": verification_result,
        "result": result_payload,
    }
