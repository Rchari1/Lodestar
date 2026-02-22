"""News and social-media sentiment analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup
from textblob import TextBlob

logger = logging.getLogger("lodestar.analysis.sentiment")

_FINVIZ_URL = "https://finviz.com/quote.ashx"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


@dataclass
class SentimentResult:
    symbol: str
    score: float = 0.0  # -1.0 (bearish) to +1.0 (bullish)
    headlines: list[str] = field(default_factory=list)
    source: str = "finviz"


def analyze_finviz_sentiment(symbol: str) -> SentimentResult:
    """Scrape Finviz news headlines and compute average sentiment."""
    result = SentimentResult(symbol=symbol, source="finviz")
    try:
        resp = requests.get(
            _FINVIZ_URL, params={"t": symbol}, headers=_HEADERS, timeout=10
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        news_table = soup.find(id="news-table")
        if not news_table:
            return result

        headlines: list[str] = []
        for row in news_table.find_all("tr")[:20]:
            link = row.find("a")
            if link:
                headlines.append(link.get_text(strip=True))

        if not headlines:
            return result

        scores = [TextBlob(h).sentiment.polarity for h in headlines]
        result.headlines = headlines
        result.score = sum(scores) / len(scores) if scores else 0.0

    except Exception:
        logger.warning("Failed to fetch Finviz sentiment for %s", symbol, exc_info=True)

    return result


def analyze_newsapi_sentiment(symbol: str, api_key: str) -> SentimentResult:
    """Use NewsAPI.org for headline sentiment (requires API key)."""
    result = SentimentResult(symbol=symbol, source="newsapi")
    if not api_key:
        return result
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": symbol,
                "sortBy": "publishedAt",
                "pageSize": 20,
                "apiKey": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        headlines = [a["title"] for a in articles if a.get("title")]
        scores = [TextBlob(h).sentiment.polarity for h in headlines]
        result.headlines = headlines
        result.score = sum(scores) / len(scores) if scores else 0.0
    except Exception:
        logger.warning("NewsAPI sentiment failed for %s", symbol, exc_info=True)
    return result


def get_combined_sentiment(symbol: str, news_api_key: str = "") -> SentimentResult:
    """Aggregate sentiment from all available sources."""
    finviz = analyze_finviz_sentiment(symbol)
    if news_api_key:
        newsapi = analyze_newsapi_sentiment(symbol, news_api_key)
        combined_score = (finviz.score + newsapi.score) / 2
        combined_headlines = finviz.headlines + newsapi.headlines
        return SentimentResult(
            symbol=symbol,
            score=combined_score,
            headlines=combined_headlines,
            source="combined",
        )
    return finviz
