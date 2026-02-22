"""Stock screener — identifies candidate tickers for analysis."""

from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("lodestar.analysis.screener")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Default watchlist if screener fails
DEFAULT_WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "META", "TSLA", "JPM", "V", "JNJ",
    "WMT", "PG", "MA", "HD", "DIS",
]


def get_top_gainers(limit: int = 10) -> list[str]:
    """Scrape Yahoo Finance for today's top gainers."""
    try:
        url = "https://finance.yahoo.com/gainers"
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        symbols: list[str] = []
        for row in soup.select("table tbody tr")[:limit]:
            cell = row.select_one("td a")
            if cell:
                symbols.append(cell.get_text(strip=True))
        return symbols or DEFAULT_WATCHLIST[:limit]
    except Exception:
        logger.warning("Failed to scrape top gainers", exc_info=True)
        return DEFAULT_WATCHLIST[:limit]


def get_most_active(limit: int = 10) -> list[str]:
    """Scrape Yahoo Finance for most-active stocks."""
    try:
        url = "https://finance.yahoo.com/most-active"
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        symbols: list[str] = []
        for row in soup.select("table tbody tr")[:limit]:
            cell = row.select_one("td a")
            if cell:
                symbols.append(cell.get_text(strip=True))
        return symbols or DEFAULT_WATCHLIST[:limit]
    except Exception:
        logger.warning("Failed to scrape most active", exc_info=True)
        return DEFAULT_WATCHLIST[:limit]


def build_watchlist(
    custom: list[str] | None = None,
    include_gainers: bool = True,
    include_active: bool = True,
    limit: int = 20,
) -> list[str]:
    """Build a de-duplicated watchlist from multiple sources."""
    symbols: list[str] = list(custom or [])
    if include_gainers:
        symbols.extend(get_top_gainers(limit=10))
    if include_active:
        symbols.extend(get_most_active(limit=10))
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for s in symbols:
        s_upper = s.upper().strip()
        if s_upper and s_upper not in seen:
            seen.add(s_upper)
            unique.append(s_upper)
    return unique[:limit]
