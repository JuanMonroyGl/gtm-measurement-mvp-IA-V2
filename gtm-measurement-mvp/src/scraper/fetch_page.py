"""Web page fetcher skeleton.

This module is intentionally simple in Phase 1 and does not perform complex
network/browser automation yet.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FetchResult:
    requested_url: str
    final_url: str | None
    status_code: int | None
    html: str | None
    warning: str | None = None


def fetch_html(target_url: str) -> FetchResult:
    """Stub fetch function for raw HTML acquisition."""
    return FetchResult(
        requested_url=target_url,
        final_url=None,
        status_code=None,
        html=None,
        warning="Fetch en modo stub: implementar requests/http client en próxima fase.",
    )
