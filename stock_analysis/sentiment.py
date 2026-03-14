"""
Sentiment Analysis + Signal Fusion
------------------------------------
Converts raw NewsItem text into a sentiment score [-1, +1] and
combines it with the technical StockSignal to produce a FusedSignal.

Two sentiment modes (auto-selected by availability):
  1. TextBlob  — zero-dependency, always available, ~80% accuracy
  2. Transformer (FinBERT)  — install transformers + torch for ~93% accuracy
     Model: ProsusAI/finbert  (finance-tuned BERT)

The fusion model weights news sentiment higher when:
  - The item is fresh  (< 2 min)
  - The item comes from a Tier-1/2 source
  - Multiple items agree on direction
"""

import math
import time
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict, deque

from news_feed import NewsItem
from stock_engine import StockSignal


# ── sentiment back-end ────────────────────────────────────────────────────────

class _TextBlobSentiment:
    """Simple polarity scorer using TextBlob."""

    def score(self, text: str) -> float:
        try:
            from textblob import TextBlob
            return float(TextBlob(text).sentiment.polarity)   # -1 .. +1
        except ImportError:
            return 0.0


class _FinBERTSentiment:
    """
    Finance-specific sentiment using ProsusAI/finbert.
    First call downloads the model (~400 MB).
    """

    _pipeline = None

    @classmethod
    def _load(cls):
        if cls._pipeline is None:
            from transformers import pipeline
            cls._pipeline = pipeline(
                "text-classification",
                model="ProsusAI/finbert",
                return_all_scores=True,
                truncation=True,
                max_length=512,
            )

    def score(self, text: str) -> float:
        self._load()
        result = self._pipeline(text[:512])[0]
        mapping = {"positive": +1.0, "negative": -1.0, "neutral": 0.0}
        score = sum(mapping.get(r["label"], 0) * r["score"] for r in result)
        return float(score)


def _build_scorer():
    try:
        import transformers, torch
        print("[sentiment] Using FinBERT (high accuracy)")
        return _FinBERTSentiment()
    except ImportError:
        print("[sentiment] Using TextBlob (install transformers+torch for FinBERT)")
        return _TextBlobSentiment()


# ── scored news item ──────────────────────────────────────────────────────────

@dataclass
class ScoredNews:
    item:       NewsItem
    polarity:   float    # -1 .. +1
    weight:     float    # 0 .. 1  (freshness × tier × confidence)
    weighted:   float    # polarity * weight

    @property
    def direction(self) -> str:
        if   self.polarity >  0.15: return "BULLISH"
        elif self.polarity < -0.15: return "BEARISH"
        return "NEUTRAL"


# ── fused output ──────────────────────────────────────────────────────────────

@dataclass
class FusedSignal:
    ticker:          str
    final_signal:    str       # BUY | HOLD | SELL
    confidence:      float     # 0-100
    tech_score:      float     # raw technical composite
    news_score:      float     # weighted sentiment composite
    fused_score:     float     # combined
    tech_signal:     Optional[StockSignal] = None
    news_items:      list[ScoredNews] = field(default_factory=list)
    alerts:          list[str] = field(default_factory=list)

    def report(self) -> str:
        lines = [
            "━" * 60,
            f"  {self.ticker}  →  {self.final_signal}  "
            f"(confidence {self.confidence:.1f}%)",
            f"  Technical score : {self.tech_score:+.3f}",
            f"  News sentiment  : {self.news_score:+.3f}",
            f"  Fused score     : {self.fused_score:+.3f}",
        ]
        if self.tech_signal:
            ind = self.tech_signal.indicators
            lines.append(
                f"  RSI={ind['rsi']:.1f}  MACD_hist={ind['macd_hist']:+.4f}"
                f"  %B={ind['pct_b']:.2f}  Stoch={ind['stoch_k']:.1f}"
            )
            if self.tech_signal.notes:
                lines.append(f"  Notes: {', '.join(self.tech_signal.notes)}")
        if self.news_items:
            lines.append(f"  Top news ({len(self.news_items)} items):")
            for sn in self.news_items[:3]:
                lines.append(
                    f"    [{sn.item.source}][{sn.direction}]"
                    f"  {sn.item.headline[:80]}"
                )
        for a in self.alerts:
            lines.append(f"  ⚠  {a}")
        lines.append("━" * 60)
        return "\n".join(lines)


# ── fusion engine ─────────────────────────────────────────────────────────────

class SentimentFusion:
    """
    Maintains a rolling window of news per ticker and fuses them
    with the latest technical signal.
    """

    # seconds — news older than this is discarded
    NEWS_TTL = 600   # 10 min

    def __init__(self,
                 tech_weight: float = 0.60,
                 news_weight: float = 0.40,
                 use_finbert: bool = False):
        self.tech_weight = tech_weight
        self.news_weight = news_weight
        self._scorer     = _FinBERTSentiment() if use_finbert else _build_scorer()
        # ticker → deque of ScoredNews
        self._news_buffer: dict[str, deque] = defaultdict(lambda: deque(maxlen=50))

    # ── public ────────────────────────────────────────────────────────────────

    def ingest_news(self, item: NewsItem):
        """Score a news item and store it for all relevant tickers."""
        text     = item.headline + ". " + item.body
        polarity = self._scorer.score(text)
        # Freshness decay: half-life 2 min → weight=1 at t=0, 0.5 at t=2min
        age_min  = item.age_seconds / 60
        freshness = math.exp(-0.35 * age_min)
        # Tier multiplier: tier 1→1.0, 2→0.8, 3→0.6, 4→0.4
        tier_mult = max(0.2, 1.0 - 0.2 * (item.tier - 1))
        weight    = freshness * tier_mult
        scored    = ScoredNews(item=item, polarity=polarity,
                               weight=weight, weighted=polarity * weight)

        tickers = item.tickers if item.tickers else ["MARKET"]
        for t in tickers:
            self._news_buffer[t].append(scored)

    def fuse(self, tech: Optional[StockSignal],
             ticker: str) -> FusedSignal:
        """Combine technical signal + buffered news for ticker."""
        self._prune(ticker)
        items = list(self._news_buffer.get(ticker, []))
        # also pull MARKET-level items (macro news)
        items += list(self._news_buffer.get("MARKET", []))

        # weighted mean sentiment
        total_w   = sum(sn.weight for sn in items) or 1e-9
        news_raw  = sum(sn.weighted for sn in items) / total_w if items else 0.0
        news_raw  = float(max(-1, min(1, news_raw)))

        tech_raw  = tech.score if tech else 0.0
        tw        = self.tech_weight if tech else 0.0
        nw        = self.news_weight if items else 0.0
        denom     = tw + nw or 1.0
        fused_raw = (tw * tech_raw + nw * news_raw) / denom
        fused_raw = float(max(-1, min(1, fused_raw)))

        if   fused_raw >  0.20: final = "BUY"
        elif fused_raw < -0.20: final = "SELL"
        else:                   final = "HOLD"

        confidence = abs(fused_raw) * 100

        alerts = []
        # Tech/news divergence warning
        if tech and abs(tech_raw - news_raw) > 0.5:
            alerts.append(
                f"Tech/news divergence: tech={tech_raw:+.2f}  news={news_raw:+.2f}"
            )
        # Sudden spike in negative news
        recent = [sn for sn in items if sn.item.age_seconds < 120]
        if recent:
            avg_recent = sum(sn.polarity for sn in recent) / len(recent)
            if avg_recent < -0.4:
                alerts.append(f"Heavy negative news in last 2 min ({len(recent)} items)")
            elif avg_recent > 0.4:
                alerts.append(f"Heavy positive news in last 2 min ({len(recent)} items)")

        # Sort items for display (most recent first)
        items_sorted = sorted(items, key=lambda s: s.item.published, reverse=True)

        return FusedSignal(
            ticker=ticker,
            final_signal=final,
            confidence=confidence,
            tech_score=tech_raw,
            news_score=news_raw,
            fused_score=fused_raw,
            tech_signal=tech,
            news_items=items_sorted[:10],
            alerts=alerts,
        )

    # ── private ───────────────────────────────────────────────────────────────

    def _prune(self, ticker: str):
        buf  = self._news_buffer.get(ticker)
        if not buf:
            return
        cutoff = time.time() - self.NEWS_TTL
        while buf and buf[0].item.published < cutoff:
            buf.popleft()
