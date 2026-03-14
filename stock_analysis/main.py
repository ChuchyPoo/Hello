"""
Stock Analysis + Real-Time News Feed  —  main entry point
==========================================================

Usage
-----
  # Quick one-shot analysis (no live news):
  python main.py --tickers AAPL TSLA NVDA MSFT --mode static

  # Live mode with RSS news (no API keys needed):
  python main.py --tickers AAPL TSLA NVDA --mode live

  # Live mode with all tiers (requires API keys in .env):
  python main.py --tickers AAPL TSLA NVDA --mode live --finbert

Speed Tiers
-----------
  Tier 1  WebSocket   < 100 ms   Alpaca / Polygon (paid)
  Tier 2  RSS         1–5 s      Reuters, CNBC, FT, WSJ, …
  Tier 3  REST API    15–60 s    Finnhub, NewsAPI, AlphaVantage
  Tier 4  Social      30–120 s   Reddit, StockTwits (extend easily)
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from colorama import Fore, Style, init as colorama_init

# local modules
from stock_engine import StockEngine
from news_feed import NewsFeedOrchestrator, NewsItem
from sentiment import SentimentFusion, FusedSignal

colorama_init(autoreset=True)
load_dotenv()

# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Stock analysis + real-time news fusion"
    )
    # Indian NSE stocks under ₹500 (append .NS for yfinance NSE tickers)
    INDIAN_STOCKS_UNDER_500 = [
        "IDEA.NS",     # Vi (Vodafone Idea)
        "YESBANK.NS",  # Yes Bank
        "SUZLON.NS",   # Suzlon Energy
        "IRFC.NS",     # Indian Railway Finance Corp
        "NHPC.NS",     # NHPC Ltd
        "RVNL.NS",     # Rail Vikas Nigam
        "SJVN.NS",     # SJVN Ltd
        "PNB.NS",      # Punjab National Bank
        "BANKBARODA.NS",# Bank of Baroda
        "CANBK.NS",    # Canara Bank
        "COALINDIA.NS",# Coal India
        "SAIL.NS",     # Steel Authority of India
        "BHEL.NS",     # Bharat Heavy Electricals
        "RECLTD.NS",   # REC Ltd
        "HUDCO.NS",    # HUDCO
        "IREDA.NS",    # IREDA
        "NBCC.NS",     # NBCC India
        "MRPL.NS",     # Mangalore Refinery
        "NATIONALUM.NS",# National Aluminium
        "GMRINFRA.NS", # GMR Airports
    ]
    p.add_argument(
        "--tickers", nargs="+",
        default=INDIAN_STOCKS_UNDER_500,
        help="Ticker symbols to watch (use .NS suffix for NSE stocks)"
    )
    p.add_argument(
        "--max-price", type=float, default=500.0,
        help="Only show stocks at or below this price in INR (default: 500)"
    )
    p.add_argument(
        "--mode", choices=["static", "live"], default="static",
        help="static=one-shot tech analysis; live=continuous with news"
    )
    p.add_argument(
        "--period", default="6mo",
        help="yfinance period for historical data (e.g. 3mo, 6mo, 1y)"
    )
    p.add_argument(
        "--interval", default="1d",
        help="yfinance bar interval (1d, 1h, 15m …)"
    )
    p.add_argument(
        "--finbert", action="store_true",
        help="Use FinBERT for sentiment (requires transformers + torch)"
    )
    p.add_argument(
        "--refresh", type=int, default=60,
        help="Seconds between technical re-analysis in live mode"
    )
    return p.parse_args()


# ── display helpers ───────────────────────────────────────────────────────────

SIGNAL_COLOR = {
    "BUY":  Fore.GREEN,
    "HOLD": Fore.YELLOW,
    "SELL": Fore.RED,
}

def _print_fused(sig: FusedSignal):
    c = SIGNAL_COLOR.get(sig.final_signal, "")
    print(c + sig.report() + Style.RESET_ALL)

def _print_news(item: NewsItem):
    tier_color = [Fore.MAGENTA, Fore.CYAN, Fore.WHITE, Fore.WHITE]
    col = tier_color[min(item.tier - 1, 3)]
    tickers = f"[{','.join(item.tickers)}]" if item.tickers else ""
    age = f"{item.age_seconds:.0f}s ago"
    print(
        col
        + f"  [{item.tier}][{item.source}] {age}  {tickers}"
        + Style.RESET_ALL
        + f"  {item.headline[:100]}"
    )

def _print_banner(tickers: list):
    print(Fore.CYAN + "=" * 60)
    print(" STOCK ANALYSIS + REAL-TIME NEWS FUSION")
    print(f" Watching: {', '.join(tickers)}")
    print("=" * 60 + Style.RESET_ALL)


# ── static mode ───────────────────────────────────────────────────────────────

def run_static(args):
    _print_banner(args.tickers)
    max_price = getattr(args, "max_price", 500.0)
    print(f"\n{Fore.WHITE}Fetching & analysing {len(args.tickers)} tickers "
          f"(max price ₹{max_price:.0f}) ...{Style.RESET_ALL}\n")

    engine  = StockEngine(period=args.period, interval=args.interval)
    fusion  = SentimentFusion(use_finbert=args.finbert)
    signals = engine.analyse_many(args.tickers)

    # filter by max price
    signals = [s for s in signals if s.last_price <= max_price]

    if not signals:
        print(Fore.RED + f"No stocks found under ₹{max_price:.0f}. "
              "Try --max-price 1000 or add more tickers." + Style.RESET_ALL)
        return

    for tech in signals:
        fused = fusion.fuse(tech, tech.ticker)
        _print_fused(fused)

    print(f"\n{Fore.CYAN}Ranked by score (best to worst) — under ₹{max_price:.0f}:{Style.RESET_ALL}")
    for i, tech in enumerate(signals, 1):
        arrow = {"BUY": "▲", "HOLD": "●", "SELL": "▼"}.get(tech.signal, "?")
        col   = SIGNAL_COLOR.get(tech.signal, "")
        print(f"  {i:2}. {col}{tech.ticker:<15}{Style.RESET_ALL}"
              f"  ₹{tech.last_price:>8.2f}  {col}{arrow} {tech.signal:<4}{Style.RESET_ALL}"
              f"  score={tech.score:+.3f}  conf={tech.confidence:.1f}%")


# ── live mode ─────────────────────────────────────────────────────────────────

async def run_live(args):
    _print_banner(args.tickers)
    tickers_set = set(t.upper() for t in args.tickers)

    env = {
        "FINNHUB_KEY":    os.getenv("FINNHUB_KEY", ""),
        "NEWSAPI_KEY":    os.getenv("NEWSAPI_KEY", ""),
        "AV_KEY":         os.getenv("AV_KEY", ""),
        "ALPACA_KEY":     os.getenv("ALPACA_KEY", ""),
        "ALPACA_SECRET":  os.getenv("ALPACA_SECRET", ""),
    }

    engine    = StockEngine(period=args.period, interval=args.interval)
    fusion    = SentimentFusion(use_finbert=args.finbert)
    news_orch = NewsFeedOrchestrator(env=env)

    # Cache of latest technical signals
    tech_cache: dict[str, object] = {}

    # ── initial technical analysis ──────────────────────────────────────────
    print(f"\n{Fore.WHITE}Running initial technical analysis ...{Style.RESET_ALL}")
    for t in args.tickers:
        sig = engine.analyse(t)
        if sig:
            tech_cache[t] = sig
            print(f"  {t}: {sig.signal}  score={sig.score:+.3f}")

    # ── start news feeds ────────────────────────────────────────────────────
    print(f"\n{Fore.CYAN}Starting news feeds ...{Style.RESET_ALL}\n")
    news_orch.start()

    last_tech_refresh = time.time()
    news_count = 0

    async def tech_refresh_loop():
        nonlocal last_tech_refresh
        while True:
            await asyncio.sleep(args.refresh)
            loop = asyncio.get_event_loop()
            for t in args.tickers:
                sig = await loop.run_in_executor(None, engine.analyse, t)
                if sig:
                    tech_cache[t] = sig
            last_tech_refresh = time.time()
            # re-print all signals after refresh
            print(f"\n{Fore.CYAN}─── Technical refresh ───{Style.RESET_ALL}")
            for t in args.tickers:
                if t in tech_cache:
                    fused = fusion.fuse(tech_cache.get(t), t)
                    _print_fused(fused)

    async def news_loop():
        nonlocal news_count
        async for item in news_orch.stream():
            news_count += 1
            # always print incoming news
            _print_news(item)
            # ingest into sentiment engine
            fusion.ingest_news(item)
            # if this item mentions a watched ticker, print updated fused signal
            relevant = tickers_set & set(item.tickers)
            for t in relevant:
                tech  = tech_cache.get(t)
                fused = fusion.fuse(tech, t)
                print(f"\n{Fore.YELLOW}  ↳ Signal update for {t}:{Style.RESET_ALL}")
                _print_fused(fused)

    # run both loops concurrently
    await asyncio.gather(
        tech_refresh_loop(),
        news_loop(),
    )


# ── entry ─────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    try:
        if args.mode == "static":
            run_static(args)
        else:
            asyncio.run(run_live(args))
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Stopped.{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
