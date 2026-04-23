"""DOM snapshot utilities with Playwright-first strategy and fetch fallback."""

from __future__ import annotations

from dataclasses import dataclass

from web_scraping.fetch_page import fetch_html

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
    fetch_warning: str | None = None


def _render_with_playwright(target_url: str) -> tuple[str | None, str | None]:
    if sync_playwright is None:
        return None, "Playwright no disponible; se usará fallback a HTML crudo."

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(target_url, wait_until="networkidle", timeout=30000)
            rendered = page.content()
            browser.close()
        return rendered, None
    except Exception as exc:  # pragma: no cover - environment-dependent
        return None, f"Falló render con Playwright; se usará fallback a HTML crudo. Detalle: {exc}"


def build_dom_snapshot(target_url: str) -> DomSnapshot:
    """Return normalized snapshot, preferring rendered DOM via Playwright."""
    if not target_url:
        return DomSnapshot(
            source_url=target_url,
            raw_html=None,
            rendered_dom_html=None,
            render_engine="none",
            warning="No hay target_url para adquirir DOM.",
            fetch_warning="No hay target_url para scraping.",
        )

    rendered_html, render_warning = _render_with_playwright(target_url)
    if rendered_html:
        return DomSnapshot(
            source_url=target_url,
            raw_html=None,
            rendered_dom_html=rendered_html,
            render_engine="playwright",
            warning=None,
            fetch_warning=None,
        )

    fetch_result = fetch_html(target_url)
    warning = render_warning or fetch_result.warning
    if fetch_result.html:
        return DomSnapshot(
            source_url=fetch_result.final_url or target_url,
            raw_html=fetch_result.html,
            rendered_dom_html=fetch_result.html,
            render_engine="raw_html_fallback",
            warning=warning,
            fetch_warning=fetch_result.warning,
        )

    return DomSnapshot(
        source_url=target_url,
        raw_html=None,
        rendered_dom_html=None,
        render_engine="none",
        warning=warning or "No fue posible adquirir DOM ni HTML crudo.",
        fetch_warning=fetch_result.warning,
    )
