"""Regression: HITL resume must reuse the live browser without re-bootstrapping."""

from __future__ import annotations

from typing import Any

import pytest

from backend.agent import browser_registry
from backend.agent.nodes import execute_actions
from backend.db.connection import get_connection
from backend.db import repository as repo


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


def test_get_or_create_session_reports_created_then_reuse(monkeypatch):
    fake = _FakeSession()
    monkeypatch.setattr(browser_registry, "BrowserSession", lambda: fake)

    session1, created1 = browser_registry.get_or_create_session("run_resume_reg")
    session2, created2 = browser_registry.get_or_create_session("run_resume_reg")

    assert created1 is True
    assert created2 is False
    assert session1 is session2
    assert fake.started == 1


def test_get_or_create_session_stops_dead_page_before_replace(monkeypatch):
    """Replacing a session with page=None must stop() the old handle (orphan-safe)."""
    dead = _FakeSession()
    dead.page = None
    dead.started = 1
    stopped: list[str] = []
    original_stop = dead.stop

    def tracking_stop() -> None:
        stopped.append("stopped")
        original_stop()

    dead.stop = tracking_stop  # type: ignore[method-assign]
    browser_registry._sessions["run_orphan"] = dead  # noqa: SLF001

    replacement = _FakeSession()
    monkeypatch.setattr(browser_registry, "BrowserSession", lambda: replacement)

    session, created = browser_registry.get_or_create_session("run_orphan")

    assert created is True
    assert session is replacement
    assert stopped == ["stopped"]
    assert replacement.started == 1


def test_initial_execute_actions_bootstraps_once(temp_db, monkeypatch):
    fake = _FakeSession()
    monkeypatch.setattr(browser_registry, "BrowserSession", lambda: fake)
    monkeypatch.setattr("backend.agent.nodes._pub", lambda *a, **k: None)

    bootstrap_calls: list[str] = []

    monkeypatch.setattr(
        "backend.agent.nodes.open_portal",
        lambda *a, **k: bootstrap_calls.append("open_portal") or {"success": True},
    )
    monkeypatch.setattr(
        "backend.agent.nodes.find_employee_in_ui",
        lambda *a, **k: bootstrap_calls.append("find_employee_in_ui")
        or {"success": True},
    )
    monkeypatch.setattr(
        "backend.agent.nodes.open_employee_detail",
        lambda *a, **k: bootstrap_calls.append("open_employee_detail")
        or {"success": True},
    )

    monkeypatch.setattr(
        "backend.agent.nodes.grant_application_via_ui",
        lambda *a, **k: {
            "success": True,
            "action_completed": True,
            "observed_state": "permission_granted",
        },
    )

    run_id = "run_bootstrap_initial"
    with get_connection() as conn:
        repo.create_run(conn, run_id, "Onboard Alex")
        repo.update_run(conn, run_id, employee_id="emp_alex", status="running")
        repo.create_action(
            conn,
            action_id="act_slack_init",
            run_id=run_id,
            employee_id="emp_alex",
            application_id="app_slack",
            requires_approval=False,
            details={"application_name": "Slack"},
        )

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

    result = execute_actions(state)

    assert bootstrap_calls == [
        "open_portal",
        "find_employee_in_ui",
        "open_employee_detail",
    ]
    assert fake.started == 1
    assert result["browser_started"] is True
    assert result["execution_status"] == "actions_complete"


def test_hitl_resume_skips_portal_bootstrap(temp_db, monkeypatch):
    """LangGraph restarts execute_actions with browser_started=False; live page skips bootstrap."""
    fake = _FakeSession()
    fake.started = 1  # already launched during the pre-HITL phase
    browser_registry._sessions["run_hitl_bootstrap"] = fake  # noqa: SLF001
    monkeypatch.setattr("backend.agent.nodes._pub", lambda *a, **k: None)

    bootstrap_calls: list[str] = []
    grant_calls: list[str] = []

    monkeypatch.setattr(
        "backend.agent.nodes.open_portal",
        lambda *a, **k: bootstrap_calls.append("open_portal") or {"success": True},
    )
    monkeypatch.setattr(
        "backend.agent.nodes.find_employee_in_ui",
        lambda *a, **k: bootstrap_calls.append("find_employee_in_ui")
        or {"success": True},
    )
    monkeypatch.setattr(
        "backend.agent.nodes.open_employee_detail",
        lambda *a, **k: bootstrap_calls.append("open_employee_detail")
        or {"success": True},
    )

    def fake_grant(session, *, employee_id, application_id, run_id, action_id):
        grant_calls.append(application_id)
        return {
            "success": True,
            "action_completed": True,
            "observed_state": "permission_granted",
        }

    monkeypatch.setattr("backend.agent.nodes.grant_application_via_ui", fake_grant)
    monkeypatch.setattr(
        "backend.agent.nodes.interrupt", lambda _payload: "approved"
    )

    run_id = "run_hitl_bootstrap"
    with get_connection() as conn:
        repo.create_run(conn, run_id, "Onboard Alex")
        repo.update_run(
            conn, run_id, employee_id="emp_alex", status="awaiting_approval"
        )
        # Completed non-privileged action must not be replayed.
        repo.create_action(
            conn,
            action_id="act_slack_done",
            run_id=run_id,
            employee_id="emp_alex",
            application_id="app_slack",
            requires_approval=False,
            details={"application_name": "Slack"},
        )
        repo.transition_action(conn, "act_slack_done", "running")
        repo.transition_action(conn, "act_slack_done", "succeeded")
        # Privileged action waiting at HITL.
        repo.create_action(
            conn,
            action_id="act_admin_wait",
            run_id=run_id,
            employee_id="emp_alex",
            application_id="app_admin",
            requires_approval=True,
            details={"application_name": "Admin Console"},
        )
        repo.transition_action(conn, "act_admin_wait", "running")
        repo.transition_action(conn, "act_admin_wait", "awaiting_approval")

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

    result = execute_actions(state)

    assert bootstrap_calls == [], (
        "HITL resume must not reopen /portal or re-run employee bootstrap navigation"
    )
    assert fake.started == 1, "must not launch a second browser"
    assert grant_calls == ["app_admin"]
    assert result["browser_started"] is True
    assert result["execution_status"] == "actions_complete"

    with get_connection() as conn:
        slack = repo.get_action(conn, "act_slack_done")
        admin = repo.get_action(conn, "act_admin_wait")
    assert slack["status"] == "succeeded"
    assert admin["status"] == "succeeded"
    assert admin["approval_decision"] == "approved"
