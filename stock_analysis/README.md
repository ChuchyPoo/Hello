# Stock Analysis + Real-Time News Feed

A multi-tier system that **analyses stocks** using technical indicators and
**fuses real-time news sentiment** to generate prioritised BUY / HOLD / SELL signals.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         main.py                                 │
│  ┌──────────────┐   ┌───────────────────┐   ┌────────────────┐  │
│  │ StockEngine  │   │ NewsFeedOrchestrat│   │ SentimentFusion│  │
│  │ (tech signals│   │ (news ingestion)  │   │ (fusion layer) │  │
│  │  RSI, MACD,  │   │                   │   │                │  │
│  │  BB, Stoch,  │   │ Tier1: WS <100ms  │   │ TextBlob /     │  │
│  │  EMA, VWAP,  │   │ Tier2: RSS  1-5s  │   │ FinBERT        │  │
│  │  ATR, Volume)│   │ Tier3: REST 15-60s│   │                │  │
│  └──────────────┘   └───────────────────┘   └────────────────┘  │
│         │                    │                       │           │
│         └────────────────────┴───────────────────────┘           │
│                          FusedSignal                             │
│                    BUY / HOLD / SELL + confidence                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Getting faster than the market

| Tier | Latency     | Source                         | Free? |
|------|-------------|--------------------------------|-------|
| 1    | **< 100 ms** | Alpaca/Polygon WebSocket stream | Free (Alpaca paper) |
| 2    | **1 – 5 s**  | RSS: Reuters, CNBC, FT, WSJ… | Always free |
| 3    | **15 – 60 s**| REST: Finnhub, NewsAPI, AlphaV | Free tier |
| 4    | **30 – 120 s**| Reddit r/wallstreetbets, StockTwits | Free |

**Key insight**: News released on a wire service (Reuters/Bloomberg) typically
reaches retail traders via their brokerage 30–120 seconds after it hits the
wire.  By connecting directly to Tier-1/2 feeds you can act in the **5–60 s
window** before most retail participants see it.

---

## Indicators computed

| Indicator | Signal logic |
|-----------|--------------|
| RSI (14)  | <30 bullish, >70 bearish |
| MACD (12/26/9) | histogram crossover direction |
| Bollinger %B | position within bands |
| Stochastic (14,3) | crossover at extremes |
| EMA 20/50/200 | trend alignment score |
| VWAP | price above/below intraday mean |
| ATR (14) | volatility context |
| Volume ratio | surge amplifies direction |

All sub-signals are **weighted and combined** into a composite score in [-1, +1].

---

## Setup

```bash
cd stock_analysis
pip install -r requirements.txt

# Optional: copy and fill API keys
cp .env.example .env
```

### Optional: high-accuracy FinBERT sentiment
```bash
pip install transformers torch
# then pass --finbert flag
```

---

## Usage

```bash
# One-shot technical analysis
python main.py --tickers AAPL TSLA NVDA MSFT --mode static

# Live mode (RSS feeds, no keys needed)
python main.py --tickers AAPL TSLA NVDA --mode live

# Live mode with all news tiers + FinBERT
python main.py --tickers AAPL TSLA NVDA --mode live --finbert

# Custom period / interval
python main.py --tickers SPY QQQ --period 1y --interval 1h --mode static
```

---

## Output example (static mode)

```
════════════════════════════════════════════════════════════
 STOCK ANALYSIS + REAL-TIME NEWS FUSION
 Watching: AAPL, MSFT, NVDA, TSLA
════════════════════════════════════════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  NVDA  →  BUY  (confidence 74.2%)
  Technical score : +0.742
  News sentiment  : +0.000
  Fused score     : +0.445
  RSI=58.3  MACD_hist=+2.1400  %B=0.68  Stoch=72.1
  Notes: Price above 200-EMA, Volume surge ×2.3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Extending

- **Add a new RSS feed**: append to `RSS_SOURCES` in `news_feed.py`
- **Add a REST API**: append to `REST_SOURCES` and add a parser function
- **Twitter/X stream**: implement a `Tier4TwitterFeed` class following the same pattern as `RSSPoller`
- **Discord/Telegram alerts**: call `_print_fused` replacement that posts to webhook

---

## Disclaimer

This software is for **educational purposes only**.
It does **not** constitute financial advice.
Always do your own research before making investment decisions.
