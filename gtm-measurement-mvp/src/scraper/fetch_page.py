"""Web page fetcher using target_url."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass
class FetchResult:
    requested_url: str
    final_url: str | None
    status_code: int | None
    html: str | None
    warning: str | None = None


def fetch_html(target_url: str) -> FetchResult:
    """Fetch raw HTML from target_url with a browser-like user agent."""
    if not target_url:
        return FetchResult(
            requested_url=target_url,
            final_url=None,
            status_code=None,
            html=None,
            warning="No hay target_url para scraping.",
        )

    request = Request(target_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=30) as response:
            html = response.read().decode("utf-8", errors="ignore")
            final_url = response.geturl()
            return FetchResult(
                requested_url=target_url,
                final_url=final_url,
                status_code=getattr(response, "status", 200),
                html=html,
                warning=None,
            )
    except URLError as exc:
        return FetchResult(
            requested_url=target_url,
            final_url=None,
            status_code=None,
            html=None,
            warning=f"Error al obtener HTML: {exc}",
        )
