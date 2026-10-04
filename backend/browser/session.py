"""Playwright browser session management."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from backend.config import PLAYWRIGHT_BASE_URL, PLAYWRIGHT_HEADLESS


class BrowserSession:
    def __init__(self, headless: bool | None = None, base_url: str | None = None) -> None:
        self.headless = PLAYWRIGHT_HEADLESS if headless is None else headless
        self.base_url = base_url or PLAYWRIGHT_BASE_URL
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None

    def start(self) -> Page:
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context()
        self.page = self._context.new_page()
        return self.page

    def stop(self) -> None:
        if self.page is not None:
            try:
                self.page.close()
            except Exception:  # noqa: BLE001
                pass
        if self._context:
            try:
                self._context.close()
            except Exception:  # noqa: BLE001
                pass
        if self._browser:
            try:
                self._browser.close()
            except Exception:  # noqa: BLE001
                pass
        if self._pw:
            self._pw.stop()
        self.page = None
        self._context = None
        self._browser = None
        self._pw = None


@contextmanager
def browser_session(
    headless: bool | None = None, base_url: str | None = None
) -> Iterator[BrowserSession]:
    session = BrowserSession(headless=headless, base_url=base_url)
    session.start()
    try:
        yield session
    finally:
        session.stop()
