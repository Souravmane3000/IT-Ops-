#!/usr/bin/env python3
"""Headed verification: bootstrap once; HITL resume must not re-open /portal."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Force headed before config import side effects in child modules.
os.environ["PLAYWRIGHT_HEADLESS"] = "false"

from backend.agent import browser_registry  # noqa: E402
from backend.agent import graph as agent_graph  # noqa: E402
from backend.agent import nodes  # noqa: E402
from backend.db.connection import get_connection  # noqa: E402
from backend.db import repository as repo  # noqa: E402
from scripts.reset_db import main as reset_main  # noqa: E402


GOAL = (
    "Onboard Alex, who is joining as a Marketing Manager. "
    "Give Alex the applications required by the company's access policy, "
    "but ask me for approval before granting any privileged access."
)


def main() -> int:
    reset_main()
    agent_graph.get_compiled_graph.cache_clear()
    browser_registry.clear_sessions()

    import backend.config as config

    print("EFFECTIVE_HEADLESS", config.PLAYWRIGHT_HEADLESS)
    if config.PLAYWRIGHT_HEADLESS:
        print("FAIL: expected headed mode")
        return 1

    # In-process run has no FastAPI event loop for SSE fan-out.
    nodes._pub = lambda *a, **k: None  # type: ignore[assignment]

    from backend.browser.session import BrowserSession

    launch_count = {"n": 0}
    _orig_start = BrowserSession.start

    def counting_start(self):
        launch_count["n"] += 1
        print(f"[LAUNCH] chromium.launch #{launch_count['n']}")
        return _orig_start(self)

    BrowserSession.start = counting_start  # type: ignore[method-assign]

    counts = {"open_portal": 0, "find_employee_in_ui": 0, "open_employee_detail": 0}
    originals = {
        "open_portal": nodes.open_portal,
        "find_employee_in_ui": nodes.find_employee_in_ui,
        "open_employee_detail": nodes.open_employee_detail,
    }

    def wrap(name):
        def _inner(*args, **kwargs):
            counts[name] += 1
            print(f"[BOOTSTRAP] {name} #{counts[name]}")
            return originals[name](*args, **kwargs)

        return _inner

    nodes.open_portal = wrap("open_portal")  # type: ignore[assignment]
    nodes.find_employee_in_ui = wrap("find_employee_in_ui")  # type: ignore[assignment]
    nodes.open_employee_detail = wrap("open_employee_detail")  # type: ignore[assignment]

    run_id = "run_headed_verify"
    with get_connection() as conn:
        repo.create_run(conn, run_id, GOAL)

    print("START", run_id)
    agent_graph.start_run(run_id, GOAL)

    with get_connection() as conn:
        run = repo.get_run(conn, run_id)
        actions = repo.list_actions_for_run(conn, run_id)
    print("AFTER_START", run["status"], [(a["application_name"], a["status"]) for a in actions])
    print("BOOTSTRAP_AFTER_START", counts)

    if run["status"] != "awaiting_approval":
        print("FAIL: expected awaiting_approval")
        browser_registry.clear_sessions()
        return 1
    if counts != {
        "open_portal": 1,
        "find_employee_in_ui": 1,
        "open_employee_detail": 1,
    }:
        print("FAIL: expected exactly one bootstrap before HITL")
        browser_registry.clear_sessions()
        return 1

    session_before, created = browser_registry.get_or_create_session(run_id)
    if created:
        print("FAIL: session should already exist before resume")
        browser_registry.clear_sessions()
        return 1

    print("RESUME approve")
    agent_graph.resume_run(run_id, "approved")

    with get_connection() as conn:
        run = repo.get_run(conn, run_id)
        actions = repo.list_actions_for_run(conn, run_id)
    print("AFTER_RESUME", run["status"], [(a["application_name"], a["status"]) for a in actions])
    print("BOOTSTRAP_AFTER_RESUME", counts)

    print("LAUNCH_COUNT", launch_count["n"])
    ok = (
        run["status"] == "complete"
        and launch_count["n"] == 1
        and counts["open_portal"] == 1
        and counts["find_employee_in_ui"] == 1
        and counts["open_employee_detail"] == 1
        and all(
            a["status"] == "succeeded"
            for a in actions
            if a["application_id"] != "app_admin" or a.get("approval_decision") == "approved"
        )
    )
    # Ensure CRM recovered
    crm = next(a for a in actions if a["application_id"] == "app_crm")
    admin = next(a for a in actions if a["application_id"] == "app_admin")
    print("CRM recovery_attempts", crm["recovery_attempts"], "status", crm["status"])
    print("ADMIN", admin["status"], admin.get("approval_decision"))

    browser_registry.clear_sessions()
    BrowserSession.start = _orig_start  # type: ignore[method-assign]

    if not ok or crm["status"] != "succeeded" or admin["status"] != "succeeded":
        print("FAIL")
        return 1
    print("PASS: 1 launch / bootstrap reused on HITL resume")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
