"""Reject privileged access → action skipped, not granted, run complete."""

from __future__ import annotations

from typing import Any

import pytest

from backend.agent import browser_registry
from backend.agent.nodes import execute_actions, verify_and_evidence
from backend.db.connection import get_connection
from backend.db import repository as repo
import backend.config as config


@pytest.fixture(autouse=True)
def _clean_registry():
    browser_registry.clear_sessions()
    yield
    browser_registry.clear_sessions()


class _FakePage:
    pass


class _FakeSession:
    def __init__(self) -> None:
        self.page: _FakePage | None = _FakePage()
        self.base_url = "http://localhost:3000"
        self.started = 0

    def start(self) -> _FakePage:
        self.started += 1
        self.page = _FakePage()
        return self.page

    def stop(self) -> None:
        self.page = None


def test_reject_admin_skips_and_run_completes(temp_db, monkeypatch):
    fake = _FakeSession()
    fake.started = 1
    browser_registry._sessions["run_reject_complete"] = fake  # noqa: SLF001
    monkeypatch.setattr("backend.agent.nodes._pub", lambda *a, **k: None)
    monkeypatch.setattr(
        "backend.agent.nodes.interrupt", lambda _payload: "rejected"
    )

    def fake_capture(session, employee_id, run_id):
        evidence_dir = config.EVIDENCE_DIR / run_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        shot = evidence_dir / "verification.png"
        shot.write_bytes(b"png")
        return {"success": True, "screenshot": str(shot)}

    monkeypatch.setattr(
        "backend.tools.verify.capture_verification_screenshot", fake_capture
    )
    monkeypatch.setattr(
        "backend.tools.verify.get_event_publisher",
        lambda: type(
            "P",
            (),
            {"publish_simple": staticmethod(lambda *a, **k: None)},
        )(),
    )

    run_id = "run_reject_complete"
    with get_connection() as conn:
        repo.create_run(conn, run_id, "Onboard Alex")
        repo.update_run(
            conn, run_id, employee_id="emp_alex", status="awaiting_approval"
        )
        for app_id, action_id in [
            ("app_github", "act_gh"),
            ("app_slack", "act_slack"),
            ("app_crm", "act_crm"),
        ]:
            repo.create_action(
                conn,
                action_id=action_id,
                run_id=run_id,
                employee_id="emp_alex",
                application_id=app_id,
                requires_approval=False,
            )
            repo.transition_action(conn, action_id, "running")
            repo.transition_action(conn, action_id, "succeeded")
            # CRM fails once by design; second grant succeeds.
            result = repo.grant_application(conn, "emp_alex", app_id, run_id=run_id)
            if not result.get("success"):
                result = repo.grant_application(
                    conn, "emp_alex", app_id, run_id=run_id
                )
            assert result.get("success") is True
        repo.create_action(
            conn,
            action_id="act_admin",
            run_id=run_id,
            employee_id="emp_alex",
            application_id="app_admin",
            requires_approval=True,
            details={"application_name": "Admin Console"},
        )
        repo.transition_action(conn, "act_admin", "running")
        repo.transition_action(conn, "act_admin", "awaiting_approval")

    state: dict[str, Any] = {
        "run_id": run_id,
        "goal": "Onboard Alex",
        "employee_id": "emp_alex",
        "employee_name": "Alex",
        "role_id": "role_marketing",
        "role_name": "Marketing Manager",
        "action_plan": [],
        "current_action_id": None,
        "approval_decision": None,
        "verification_result": None,
        "execution_status": "running",
        "error": None,
        "browser_started": False,
    }

    exec_result = execute_actions(state)
    assert exec_result["execution_status"] == "actions_complete"

    with get_connection() as conn:
        admin = repo.get_action(conn, "act_admin")
        perm = repo.get_permission(conn, "emp_alex", "app_admin")
    assert admin["status"] == "skipped"
    assert admin["approval_decision"] == "rejected"
    assert perm is None or perm["status"] != "granted"

    verify_result = verify_and_evidence({**state, **exec_result})
    assert verify_result["execution_status"] == "complete"
    assert verify_result["verification_result"]["passed"] is True

    with get_connection() as conn:
        run = repo.get_run(conn, run_id)
    assert run["status"] == "complete"
