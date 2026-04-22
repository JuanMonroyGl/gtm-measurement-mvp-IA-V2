"""DOM snapshot utilities with optional JS-rendered fallback."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # optional dependency
    sync_playwright = None  # type: ignore[assignment]


@dataclass
class DomSnapshot:
    source_url: str
    raw_html: str | None
    rendered_dom_html: str | None
    render_engine: str
    warning: str | None = None


def _render_with_playwright(target_url: str) -> tuple[str | None, str | None]:
    if sync_playwright is None:
        return None, "Playwright no disponible; se usa HTML crudo."

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(target_url, wait_until="networkidle", timeout=30000)
            rendered = page.content()
            browser.close()
        return rendered, None
    except Exception as exc:  # pragma: no cover - environment-dependent
        return None, f"No fue posible renderizar DOM con Playwright: {exc}"


def build_dom_snapshot(target_url: str, raw_html: str | None) -> DomSnapshot:
    """Return normalized snapshot, preferring rendered DOM when possible."""
    rendered_html: str | None = None
    warning: str | None = None

    if target_url:
        rendered_html, warning = _render_with_playwright(target_url)

    if rendered_html:
        return DomSnapshot(
            source_url=target_url,
            raw_html=raw_html,
            rendered_dom_html=rendered_html,
            render_engine="playwright",
            warning=warning,
        )

    return DomSnapshot(
        source_url=target_url,
        raw_html=raw_html,
        rendered_dom_html=raw_html,
        render_engine="raw_html_fallback",
        warning=warning or "Snapshot renderizado no disponible; se usa HTML crudo.",
    )
