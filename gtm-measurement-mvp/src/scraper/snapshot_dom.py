"""DOM snapshot skeleton prepared for rendered pages.

In future phases this module should support browser-based rendering
(e.g., Playwright/Selenium) to capture post-JS DOM.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DomSnapshot:
    source_url: str
    raw_html: str | None
    rendered_dom_html: str | None
    render_engine: str
    warning: str | None = None


def build_dom_snapshot(target_url: str, raw_html: str | None) -> DomSnapshot:
    """Return a normalized snapshot object with rendered-DOM placeholders."""
    return DomSnapshot(
        source_url=target_url,
        raw_html=raw_html,
        rendered_dom_html=None,
        render_engine="stub_browser_renderer",
        warning="Snapshot renderizado no implementado en esta fase.",
    )
