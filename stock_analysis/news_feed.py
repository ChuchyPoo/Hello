"""
Real-Time News Feed Ingestion
------------------------------
Strategy for maximum speed-to-market:

  Tier-1  (< 100 ms)  WebSocket streams  — Alpaca, Polygon.io news WS
  Tier-2  (1–5 s)     RSS polling loop   — Reuters, Bloomberg, CNBC, FT, WSJ
  Tier-3  (30–60 s)   REST APIs          — NewsAPI, GNews, Finnhub, Alpha Vantage
  Tier-4  (event)     Reddit / Twitter   — r/wallstreetbets, StockTwits

All inbound items are normalised into a NewsItem dataclass and pushed onto a
shared asyncio.Queue so the fusion layer can react instantly.

NOTE: Replace placeholder API keys in .env before running.
"""

import asyncio
import time
import json
import hashlib
from dataclasses import dataclass, field
from typing import Optional
import aiohttp
import feedparser
from datetime import datetime, timezone


# ── data model ───────────────────────────────────────────────────────────────

@dataclass
class NewsItem:
    source:     str
    tier:       int          # 1=fastest … 4=slowest
    headline:   str
    body:       str
    url:        str
    published:  float        # unix timestamp
    tickers:    list[str] = field(default_factory=list)   # extracted mentions
    raw:        dict = field(default_factory=dict)

    @property
    def uid(self) -> str:
        """Stable dedup key."""
        return hashlib.md5(self.headline.encode()).hexdigest()

    @property
    def age_seconds(self) -> float:
        return time.time() - self.published


# ── RSS / REST sources ────────────────────────────────────────────────────────

RSS_SOURCES = [
    # General market / macro
    ("Reuters Business",  "https://feeds.reuters.com/reuters/businessNews"),
    ("CNBC Top News",     "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("FT Markets",        "https://www.ft.com/markets?format=rss"),
    ("WSJ Markets",       "https://feeds.content.dowjones.io/public/rss/mktw_realtimeheadlines"),
    ("Seeking Alpha",     "https://seekingalpha.com/market_currents.xml"),
    ("Benzinga",          "https://www.benzinga.com/feed"),
    ("Yahoo Finance",     "https://finance.yahoo.com/news/rssindex"),
    ("MarketWatch",       "https://feeds.marketwatch.com/marketwatch/topstories/"),
    # Macro / geopolitical
    ("BBC Business",      "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("AP Finance",        "https://rsshub.app/apnews/topics/financial-markets"),
    # Crypto (cross-asset)
    ("CoinDesk",          "https://www.coindesk.com/arc/outboundfeeds/rss/"),
]

# REST polling endpoints (add keys via environment variables)
REST_SOURCES = [
    {
        "name": "Finnhub",
        "url": "https://finnhub.io/api/v1/news?category=general&token={FINNHUB_KEY}",
        "interval": 15,
        "tier": 3,
        "parser": "finnhub",
    },
    {
        "name": "NewsAPI",
        "url": (
            "https://newsapi.org/v2/top-headlines"
            "?category=business&pageSize=20&apiKey={NEWSAPI_KEY}"
        ),
        "interval": 30,
        "tier": 3,
        "parser": "newsapi",
    },
    {
        "name": "Alpha Vantage News",
        "url": (
            "https://www.alphavantage.co/query"
            "?function=NEWS_SENTIMENT&topics=financial_markets"
            "&limit=20&apikey={AV_KEY}"
        ),
        "interval": 60,
        "tier": 3,
        "parser": "alphavantage",
    },
]

# Common stock ticker symbols to scan for in headlines
KNOWN_TICKERS = {
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "TSLA",
    "BRK", "UNH", "JPM", "V", "XOM", "JNJ", "WMT", "MA", "PG",
    "AVGO", "HD", "CVX", "LLY", "MRK", "ABBV", "PEP", "KO",
    "BABA", "TSM", "AMD", "INTC", "NFLX", "DIS", "CRM", "ORCL",
    "SPY", "QQQ", "IWM", "DIA",
}


def _extract_tickers(text: str) -> list[str]:
    """Crude but fast: scan for known ticker symbols surrounded by non-alpha chars."""
    import re
    words = set(re.findall(r'\b[A-Z]{1,5}\b', text))
    return sorted(words & KNOWN_TICKERS)


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


# ── parsers ───────────────────────────────────────────────────────────────────

def _parse_rss_entry(entry, source_name: str) -> NewsItem:
    published = _now_ts()
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            published = time.mktime(entry.published_parsed)
        except Exception:
            pass
    headline = getattr(entry, "title", "")
    body     = getattr(entry, "summary", "")
    url      = getattr(entry, "link", "")
    return NewsItem(
        source=source_name, tier=2,
        headline=headline, body=body, url=url,
        published=published,
        tickers=_extract_tickers(headline + " " + body),
    )


def _parse_finnhub(data: list) -> list[NewsItem]:
    items = []
    for d in data:
        items.append(NewsItem(
            source="Finnhub", tier=3,
            headline=d.get("headline", ""),
            body=d.get("summary", ""),
            url=d.get("url", ""),
            published=d.get("datetime", _now_ts()),
            tickers=[d["related"]] if d.get("related") else
                     _extract_tickers(d.get("headline", "")),
            raw=d,
        ))
    return items


def _parse_newsapi(data: dict) -> list[NewsItem]:
    items = []
    for a in data.get("articles", []):
        published = _now_ts()
        try:
            from dateutil.parser import parse as dp
            published = dp(a["publishedAt"]).timestamp()
        except Exception:
            pass
        headline = a.get("title", "")
        body     = a.get("description", "") or ""
        items.append(NewsItem(
            source="NewsAPI", tier=3,
            headline=headline, body=body,
            url=a.get("url", ""),
            published=published,
            tickers=_extract_tickers(headline + " " + body),
            raw=a,
        ))
    return items


def _parse_alphavantage(data: dict) -> list[NewsItem]:
    items = []
    for f in data.get("feed", []):
        published = _now_ts()
        try:
            published = datetime.strptime(
                f["time_published"], "%Y%m%dT%H%M%S"
            ).replace(tzinfo=timezone.utc).timestamp()
        except Exception:
            pass
        tickers = [t["ticker"] for t in f.get("ticker_sentiment", [])
                   if t.get("ticker")]
        items.append(NewsItem(
            source="AlphaVantage", tier=3,
            headline=f.get("title", ""),
            body=f.get("summary", ""),
            url=f.get("url", ""),
            published=published,
            tickers=tickers or _extract_tickers(f.get("title", "")),
            raw=f,
        ))
    return items


PARSERS = {
    "finnhub":      _parse_finnhub,
    "newsapi":      _parse_newsapi,
    "alphavantage": _parse_alphavantage,
}


# ── WebSocket tier-1 (Alpaca / Polygon stub) ──────────────────────────────────

class WebSocketNewsFeed:
    """
    Tier-1: connects to a streaming news WebSocket (Alpaca or Polygon).
    Replace WS_URL and AUTH with real credentials.

    Alpaca  : wss://stream.data.alpaca.markets/v1beta1/news
    Polygon : wss://delayed.polygon.io/v2   (free) or wss://socket.polygon.io/v2 (paid)
    """

    WS_URL = "wss://stream.data.alpaca.markets/v1beta1/news"

    def __init__(self, api_key: str, api_secret: str, queue: asyncio.Queue):
        self.api_key    = api_key
        self.api_secret = api_secret
        self.queue      = queue

    async def run(self):
        import websockets  # pip install websockets
        backoff = 1
        while True:
            try:
                async with websockets.connect(self.WS_URL) as ws:
                    # authenticate
                    await ws.send(json.dumps({
                        "action": "auth",
                        "key":    self.api_key,
                        "secret": self.api_secret,
                    }))
                    # subscribe to all news
                    await ws.send(json.dumps({
                        "action": "subscribe",
                        "news":   ["*"],
                    }))
                    backoff = 1
                    async for msg in ws:
                        events = json.loads(msg)
                        for ev in events:
                            if ev.get("T") == "n":   # news event
                                item = NewsItem(
                                    source="Alpaca-WS", tier=1,
                                    headline=ev.get("headline", ""),
                                    body=ev.get("summary", ""),
                                    url=ev.get("url", ""),
                                    published=time.time(),
                                    tickers=ev.get("symbols", []),
                                    raw=ev,
                                )
                                await self.queue.put(item)
            except Exception as e:
                print(f"[WS] disconnected: {e}  retrying in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)


# ── RSS poller ────────────────────────────────────────────────────────────────

class RSSPoller:
    """Tier-2: polls RSS feeds concurrently on a tight interval."""

    def __init__(self, queue: asyncio.Queue, interval: float = 5.0):
        self.queue    = queue
        self.interval = interval
        self._seen: set[str] = set()

    async def run(self):
        while True:
            tasks = [self._poll_one(name, url) for name, url in RSS_SOURCES]
            await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(self.interval)

    async def _poll_one(self, name: str, url: str):
        loop = asyncio.get_event_loop()
        try:
            feed = await loop.run_in_executor(None, feedparser.parse, url)
            for entry in feed.entries:
                item = _parse_rss_entry(entry, name)
                if item.uid not in self._seen:
                    self._seen.add(item.uid)
                    # keep seen-set bounded
                    if len(self._seen) > 10_000:
                        self._seen = set(list(self._seen)[-5_000:])
                    await self.queue.put(item)
        except Exception as e:
            pass   # silent — will retry next cycle


# ── REST poller ───────────────────────────────────────────────────────────────

class RESTPoller:
    """Tier-3: polls REST APIs on configurable intervals."""

    def __init__(self, queue: asyncio.Queue, env: dict):
        self.queue = queue
        self.env   = env
        self._seen: set[str] = set()

    async def run(self):
        tasks = [self._poll_source(src) for src in REST_SOURCES]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _poll_source(self, src: dict):
        async with aiohttp.ClientSession() as session:
            while True:
                url = src["url"].format(**self.env)
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                        data = await r.json(content_type=None)
                    parser = PARSERS.get(src["parser"])
                    if parser:
                        items = parser(data)
                        for item in items:
                            if item.uid not in self._seen:
                                self._seen.add(item.uid)
                                await self.queue.put(item)
                except Exception:
                    pass
                await asyncio.sleep(src["interval"])


# ── orchestrator ──────────────────────────────────────────────────────────────

class NewsFeedOrchestrator:
    """
    Starts all feed tiers and exposes a single async generator
    that yields NewsItem objects ordered by arrival time (fastest first).

    Usage:
        async for item in orchestrator.stream():
            process(item)
    """

    def __init__(self, env: Optional[dict] = None):
        self.env   = env or {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []

    def start(self):
        """Launch background feed tasks (call inside an asyncio event loop)."""
        # Tier 2 — RSS (always on)
        rss = RSSPoller(self.queue, interval=5.0)
        self._tasks.append(asyncio.create_task(rss.run()))

        # Tier 3 — REST (only if keys provided)
        if any(k in self.env for k in ("FINNHUB_KEY", "NEWSAPI_KEY", "AV_KEY")):
            rest = RESTPoller(self.queue, self.env)
            self._tasks.append(asyncio.create_task(rest.run()))

        # Tier 1 — WebSocket (only if Alpaca creds provided)
        if self.env.get("ALPACA_KEY") and self.env.get("ALPACA_SECRET"):
            ws = WebSocketNewsFeed(
                self.env["ALPACA_KEY"], self.env["ALPACA_SECRET"], self.queue
            )
            self._tasks.append(asyncio.create_task(ws.run()))

    async def stream(self):
        """Async generator — yields items as they arrive."""
        while True:
            item = await self.queue.get()
            yield item

    def stop(self):
        for t in self._tasks:
            t.cancel()
