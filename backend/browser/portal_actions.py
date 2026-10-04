"""Deterministic Playwright actions against the synthetic IT portal UI.

IMPORTANT: Grants are performed only through the visible portal UI.
This module must never call the grant API directly or mutate SQLite permissions.
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from backend.browser.session import BrowserSession
from backend.evidence.writer import screenshot_path


def _result(
    *,
    success: bool,
    error: str | None = None,
    screenshot: str | None = None,
    observed_state: str | None = None,
    action_completed: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "success": success,
        "error": error,
        "screenshot_path": screenshot,
        "observed_state": observed_state,
        "action_completed": action_completed,
    }
    if extra:
        payload.update(extra)
    return payload


def _capture(page: Page, run_id: str, name: str) -> str:
    path = screenshot_path(run_id, name)
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def _is_ui_granted(status_text: str) -> bool:
    """Parse portal permission label without matching substring of 'Not granted'."""
    normalized = " ".join(status_text.strip().lower().split())
    if normalized in {"not granted", "not_granted", "absent", "revoked"}:
        return False
    return normalized == "granted"


def open_portal(session: BrowserSession, run_id: str) -> dict[str, Any]:
    assert session.page is not None
    page = session.page
    url = f"{session.base_url}/portal"
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-testid="portal-home"]', timeout=15000)
    shot = _capture(page, run_id, "portal_home")
    return _result(
        success=True,
        screenshot=shot,
        observed_state="portal_open",
        action_completed=True,
    )


def find_employee_in_ui(
    session: BrowserSession, employee_id: str, run_id: str
) -> dict[str, Any]:
    assert session.page is not None
    page = session.page
    url = f"{session.base_url}/portal/employees"
    page.goto(url, wait_until="domcontentloaded")
    selector = f'[data-testid="employee-row-{employee_id}"]'
    try:
        page.wait_for_selector(selector, timeout=15000)
    except PlaywrightTimeoutError:
        shot = _capture(page, run_id, f"employee_not_found_{employee_id}")
        return _result(
            success=False,
            error=f"Employee {employee_id} not found in portal UI",
            screenshot=shot,
            observed_state="employee_not_found",
        )
    shot = _capture(page, run_id, f"employee_list_{employee_id}")
    return _result(
        success=True,
        screenshot=shot,
        observed_state="employee_found",
        action_completed=True,
    )


def open_employee_detail(
    session: BrowserSession, employee_id: str, run_id: str
) -> dict[str, Any]:
    assert session.page is not None
    page = session.page
    url = f"{session.base_url}/portal/employees/{employee_id}"
    detail_sel = f'[data-testid="employee-detail-{employee_id}"]'
    # Skip redundant goto when already on this employee detail (reduces nav flash).
    current = page.url.split("?")[0].rstrip("/")
    target = url.rstrip("/")
    if current != target:
        page.goto(
            url,
            wait_until="domcontentloaded",
        )
    page.wait_for_selector(detail_sel, timeout=15000)
    shot = _capture(page, run_id, f"employee_detail_{employee_id}")
    return _result(
        success=True,
        screenshot=shot,
        observed_state="employee_detail_open",
        action_completed=True,
    )


def grant_application_via_ui(
    session: BrowserSession,
    *,
    employee_id: str,
    application_id: str,
    run_id: str,
    action_id: str,
) -> dict[str, Any]:
    """Click the portal Grant button — never call the grant API from here."""
    assert session.page is not None
    page = session.page

    # Ensure we are on the employee detail page
    open_employee_detail(session, employee_id, run_id)

    grant_btn = f'[data-testid="grant-btn-{application_id}"]'
    status_sel = f'[data-testid="permission-status-{application_id}"]'
    error_sel = '[data-testid="grant-error"]'

    try:
        page.wait_for_selector(grant_btn, timeout=10000)
    except PlaywrightTimeoutError:
        # Button may be absent if already granted — check status
        try:
            status_text = page.locator(status_sel).inner_text(timeout=3000).strip().lower()
            if _is_ui_granted(status_text):
                shot = _capture(page, run_id, f"{action_id}_already_granted")
                return _result(
                    success=True,
                    screenshot=shot,
                    observed_state="permission_granted",
                    action_completed=True,
                )
        except PlaywrightTimeoutError:
            pass
        shot = _capture(page, run_id, f"{action_id}_no_grant_button")
        return _result(
            success=False,
            error="Grant button not found",
            screenshot=shot,
            observed_state="grant_button_missing",
        )

    # Capture current grant sequence so we wait for a new attempt result.
    state_el = page.locator('[data-testid="grant-state"]')
    try:
        prev_seq = int(state_el.get_attribute("data-seq") or "0")
    except Exception:  # noqa: BLE001
        prev_seq = 0

    page.click(grant_btn)

    # Wait until grant-state leaves pending for a newer sequence.
    try:
        page.wait_for_function(
            """([prevSeq]) => {
                const el = document.querySelector('[data-testid="grant-state"]');
                if (!el) return false;
                const seq = Number(el.getAttribute('data-seq') || '0');
                const state = el.getAttribute('data-state');
                if (seq > prevSeq && (state === 'success' || state === 'error')) return state;
                return false;
            }""",
            arg=[prev_seq],
            timeout=20000,
        )
    except PlaywrightTimeoutError:
        shot = _capture(page, run_id, f"{action_id}_timeout")
        return _result(
            success=False,
            error="Timed out waiting for grant result in UI",
            screenshot=shot,
            observed_state="timeout",
        )

    state = page.locator('[data-testid="grant-state"]').get_attribute("data-state")
    if state == "error":
        error_text = ""
        if page.locator(error_sel).count() > 0:
            error_text = page.locator(error_sel).inner_text().strip()
        shot = _capture(page, run_id, f"{action_id}_failed")
        return _result(
            success=False,
            error=error_text or "Grant failed",
            screenshot=shot,
            observed_state="grant_failed",
            action_completed=False,
        )

    status_text = page.locator(status_sel).inner_text().strip().lower()
    shot = _capture(page, run_id, f"{action_id}")
    if _is_ui_granted(status_text) or state == "success":
        return _result(
            success=True,
            screenshot=shot,
            observed_state="permission_granted",
            action_completed=True,
        )

    return _result(
        success=False,
        error=f"Unexpected permission status: {status_text}",
        screenshot=shot,
        observed_state=status_text,
    )


def read_permission_from_ui(
    session: BrowserSession,
    *,
    employee_id: str,
    application_id: str,
    run_id: str,
) -> dict[str, Any]:
    assert session.page is not None
    page = session.page
    open_employee_detail(session, employee_id, run_id)
    status_sel = f'[data-testid="permission-status-{application_id}"]'
    try:
        text = page.locator(status_sel).inner_text(timeout=5000).strip().lower()
    except PlaywrightTimeoutError:
        shot = _capture(page, run_id, f"perm_read_missing_{application_id}")
        return _result(
            success=True,
            screenshot=shot,
            observed_state="not_granted",
            action_completed=True,
            extra={"ui_status": "not_granted"},
        )

    observed = "permission_granted" if _is_ui_granted(text) else "not_granted"
    shot = _capture(page, run_id, f"perm_read_{application_id}")
    return _result(
        success=True,
        screenshot=shot,
        observed_state=observed,
        action_completed=True,
        extra={"ui_status": observed},
    )


def capture_verification_screenshot(
    session: BrowserSession, employee_id: str, run_id: str
) -> dict[str, Any]:
    assert session.page is not None
    open_employee_detail(session, employee_id, run_id)
    path = screenshot_path(run_id, "verification")
    session.page.screenshot(path=str(path), full_page=True)
    return _result(
        success=True,
        screenshot=str(path),
        observed_state="verification_captured",
        action_completed=True,
    )
