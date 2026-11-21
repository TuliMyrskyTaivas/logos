from __future__ import annotations

import urllib.request

USER_AGENT = "eign/0.1 (private portfolio service)"


def fetch_text(url: str, timeout: float = 20.0) -> str:
    """Fetch a URL and return the decoded body.

    Both MOEX ISS and CBR reject requests without a browser-like user agent.
    """
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


class TextFetcherImpl:
    """Fetcher bound to a specific timeout."""

    def __init__(self, timeout: float) -> None:
        self._timeout = timeout

    def __call__(self, url: str) -> str:
        return fetch_text(url, timeout=self._timeout)


def make_fetcher(timeout: float) -> TextFetcherImpl:
    """Return a fetcher bound to a specific timeout."""
    return TextFetcherImpl(timeout)
