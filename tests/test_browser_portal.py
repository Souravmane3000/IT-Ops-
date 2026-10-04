"""Browser smoke test against the synthetic portal (requires running frontend)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from backend.browser.portal_actions import grant_application_via_ui, open_portal
from backend.browser.session import browser_session
from backend.main import app


@pytest.mark.skipif(
    os.getenv("RUN_BROWSER_TESTS", "0") != "1",
    reason="Set RUN_BROWSER_TESTS=1 with frontend on PLAYWRIGHT_BASE_URL",
)
def test_grant_github_via_ui(temp_db, monkeypatch):
    monkeypatch.setenv("PLAYWRIGHT_HEADLESS", "true")
    import backend.config as config

    monkeypatch.setattr(config, "PLAYWRIGHT_HEADLESS", True)

    # Ensure portal API serves the temp DB while Playwright drives the UI.
    with TestClient(app) as _client:
        pass

    with browser_session(headless=True) as session:
        opened = open_portal(session, "run_browser_smoke")
        assert opened["success"] is True
        result = grant_application_via_ui(
            session,
            employee_id="emp_alex",
            application_id="app_github",
            run_id="run_browser_smoke",
            action_id="act_browser_github",
        )
        assert result["success"] is True
        assert result["observed_state"] == "permission_granted"
