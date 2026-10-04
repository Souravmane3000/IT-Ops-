"""Per-run Playwright session registry (process-local)."""

from __future__ import annotations

from backend.browser.session import BrowserSession

_sessions: dict[str, BrowserSession] = {}


def get_or_create_session(run_id: str) -> tuple[BrowserSession, bool]:
    """Return (session, created). created=True only when a new browser was launched."""
    session = _sessions.get(run_id)
    if session is not None and session.page is not None:
        return session, False

    # Dead/partial session: close before replacing to avoid orphan Chromium windows.
    if session is not None:
        try:
            session.stop()
        except Exception:  # noqa: BLE001
            pass
        _sessions.pop(run_id, None)

    session = BrowserSession()
    session.start()
    _sessions[run_id] = session
    return session, True


def close_session(run_id: str) -> None:
    session = _sessions.pop(run_id, None)
    if session is not None:
        session.stop()


def clear_sessions() -> None:
    """Test helper: stop and drop all registered sessions."""
    for run_id in list(_sessions.keys()):
        close_session(run_id)
