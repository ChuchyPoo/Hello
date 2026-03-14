"""
Stock Analysis + Real-Time News Feed  —  main entry point
==========================================================

Usage
-----
  # One-shot with reasoning:
  python main.py --mode static --show-reasoning

  # With historical pattern matches:
  python main.py --mode static --historical

  # Scan all NSE stocks under 500:
  python main.py --scan-all --max-price 500

  # Scan a sector:
  python main.py --sector banks --mode static

  # Launch web dashboard:
  python main.py --web

  # Paper trading:
  python main.py --mode static --broker paper

  # Live mode with news:
  python main.py --mode live
"""

import argparse
import asyncio
import os
import sys
import time
from dotenv import load_dotenv
from colorama import Fore, Style, init as colorama_init

from stock_engine import StockEngine, THRESHOLDS
from news_feed import NewsFeedOrchestrator, NewsItem
from sentiment import SentimentFusion, FusedSignal
from nse_stocks import (
    NSE_STOCKS, SECTOR_LIST, get_all_tickers, get_by_sector, get_by_sectors
)
from historical import HistoricalPatternMatcher, summarize_matches

colorama_init(autoreset=True)
load_dotenv()


# ── default tickers ───────────────────────────────────────────────────────────

DEFAULT_TICKERS = [
    # Priority picks
    "TITAGARH.NS", "APOLLOTYRE.NS", "ETERNAL.NS", "HINDCOPPER.NS",
    # Other good NSE stocks
    "IRFC.NS", "RVNL.NS", "SUZLON.NS", "NHPC.NS", "SJVN.NS",
    "RECLTD.NS", "HUDCO.NS", "IREDA.NS", "NBCC.NS", "PNB.NS",
    "BANKBARODA.NS", "CANBK.NS", "COALINDIA.NS", "SAIL.NS",
    "NATIONALUM.NS", "GMRINFRA.NS",
]


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Stock analysis + real-time news fusion"
    )
    p.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS,
                   help="Ticker symbols (use .NS for NSE)")
    p.add_argument("--max-price", type=float, default=1000.0,
                   help="Max price filter in INR (default: 1000)")
    p.add_argument("--mode", choices=["static", "live"], default="static",
                   help="static=one-shot; live=continuous with news")
    p.add_argument("--period", default="6mo",
                   help="yfinance period (3mo, 6mo, 1y, 2y)")
    p.add_argument("--interval", default="1d",
                   help="yfinance bar interval (1d, 1h, 15m)")
    p.add_argument("--finbert", action="store_true",
                   help="Use FinBERT for sentiment")
    p.add_argument("--refresh", type=int, default=60,
                   help="Seconds between re-analysis in live mode")

    # New flags
    p.add_argument("--scan-all", action="store_true",
                   help="Scan all NSE stocks from the database")
    p.add_argument("--sector", nargs="+",
                   help=f"Filter by sector(s): {', '.join(SECTOR_LIST)}")
    p.add_argument("--show-reasoning", action="store_true",
                   help="Print full decision reasoning for each stock")
    p.add_argument("--historical", action="store_true",
                   help="Show historical pattern matches")
    p.add_argument("--web", action="store_true",
                   help="Launch Flask web dashboard instead of CLI")
    p.add_argument("--broker", choices=["paper", "zerodha", "angelone"],
                   default="paper", help="Broker for trading")
    p.add_argument("--live-trade", action="store_true",
                   help="Enable live trading (REAL MONEY)")
    p.add_argument("--capital", type=float, default=100_000,
                   help="Trading capital in INR (default: 100000)")

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

def _print_banner(tickers: list, title: str = ""):
    print(Fore.CYAN + "=" * 60)
    print(f" STOCK ANALYSIS{' - ' + title if title else ''}")
    if len(tickers) <= 10:
        print(f" Watching: {', '.join(t.replace('.NS','') for t in tickers)}")
    else:
        print(f" Watching: {len(tickers)} stocks")
    print("=" * 60 + Style.RESET_ALL)

def _print_thresholds():
    T = THRESHOLDS
    print(Fore.CYAN + "\n  Signal Thresholds:" + Style.RESET_ALL)
    print(f"    BUY  : composite score > +{T['BUY_THRESHOLD']}")
    print(f"    SELL : composite score < {T['SELL_THRESHOLD']}")
    print(f"    HOLD : between {T['SELL_THRESHOLD']} and +{T['BUY_THRESHOLD']}")
    print(f"    RSI  : <{T['RSI_STRONG_OVERSOLD']} oversold, >{T['RSI_STRONG_OVERBOUGHT']} overbought")
    print(f"    Stoch: <{T['STOCH_OVERSOLD']} oversold, >{T['STOCH_OVERBOUGHT']} overbought")
    print(f"    Weights: RSI={T['W_RSI']:.0%} MACD={T['W_MACD']:.0%} BB={T['W_BOLLINGER']:.0%} "
          f"Stoch={T['W_STOCH']:.0%} EMA={T['W_EMA_TREND']:.0%} VWAP={T['W_VWAP']:.0%} Vol={T['W_VOLUME']:.0%}")
    print()


# ── static mode ───────────────────────────────────────────────────────────────

def run_static(args):
    _print_banner(args.tickers)
    _print_thresholds()
    max_price = args.max_price

    print(f"{Fore.WHITE}Fetching & analysing {len(args.tickers)} tickers "
          f"(max price Rs.{max_price:.0f}) ...{Style.RESET_ALL}\n")

    engine  = StockEngine(period=args.period, interval=args.interval)
    fusion  = SentimentFusion(use_finbert=args.finbert)
    matcher = HistoricalPatternMatcher() if args.historical else None
    signals = engine.analyse_many(args.tickers)

    # filter by max price
    signals = [s for s in signals if s.last_price <= max_price]

    if not signals:
        print(Fore.RED + f"No stocks found under Rs.{max_price:.0f}. "
              "Try --max-price 2000 or --scan-all" + Style.RESET_ALL)
        return

    for tech in signals:
        fused = fusion.fuse(tech, tech.ticker)
        _print_fused(fused)

        # Show reasoning
        if args.show_reasoning:
            col = SIGNAL_COLOR.get(tech.signal, "")
            print(col + tech.full_reasoning() + Style.RESET_ALL)
            print()

        # Show historical matches
        if matcher:
            matches = matcher.find_matches(tech)
            summary = summarize_matches(matches)
            print(Fore.CYAN + summary + Style.RESET_ALL)
            print()

    # Ranked summary
    print(f"\n{Fore.CYAN}Ranked by score (best to worst) — under Rs.{max_price:.0f}:{Style.RESET_ALL}")
    for i, tech in enumerate(signals, 1):
        arrow = {"BUY": "^", "HOLD": "-", "SELL": "v"}.get(tech.signal, "?")
        col   = SIGNAL_COLOR.get(tech.signal, "")
        print(f"  {i:2}. {col}{tech.ticker:<15}{Style.RESET_ALL}"
              f"  Rs.{tech.last_price:>8.2f}  {col}{arrow} {tech.signal:<4}{Style.RESET_ALL}"
              f"  score={tech.score:+.3f}  conf={tech.confidence:.1f}%")

    # Auto-trade if broker specified
    if args.broker != "paper" or args.live_trade:
        _run_auto_trade(args, signals)


def _run_auto_trade(args, signals):
    from auto_trader import AutoTrader, PositionSizer, BROKER_REGISTRY

    if args.live_trade:
        print(f"\n{Fore.RED}WARNING: LIVE TRADING WITH REAL MONEY!{Style.RESET_ALL}")
        confirm = input("Type YES to confirm: ")
        if confirm != "YES":
            print("Cancelled.")
            return

    BrokerClass = BROKER_REGISTRY.get(args.broker)
    if not BrokerClass:
        print(f"Unknown broker: {args.broker}")
        return

    broker_instance = BrokerClass() if args.broker != "paper" \
        else BrokerClass(capital=args.capital)
    if not broker_instance.connect():
        print("Broker connection failed.")
        return

    sizer  = PositionSizer(capital=args.capital)
    auto   = AutoTrader(broker=broker_instance, sizer=sizer,
                        dry_run=not args.live_trade)

    for sig in signals:
        order = auto.evaluate_and_trade(sig)
        if order:
            col = Fore.GREEN if order.action == "BUY" else Fore.RED
            print(f"  {col}[{order.status}] {order.action} {order.quantity} x "
                  f"{order.ticker} @ Rs.{order.price:.2f}  "
                  f"SL={order.stop_loss:.2f} TP={order.take_profit:.2f}"
                  f"{Style.RESET_ALL}")


# ── live mode ─────────────────────────────────────────────────────────────────

async def run_live(args):
    _print_banner(args.tickers, "LIVE")
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

    tech_cache: dict[str, object] = {}

    print(f"\n{Fore.WHITE}Running initial technical analysis ...{Style.RESET_ALL}")
    for t in args.tickers:
        sig = engine.analyse(t)
        if sig:
            tech_cache[t] = sig
            print(f"  {t}: {sig.signal}  score={sig.score:+.3f}")

    print(f"\n{Fore.CYAN}Starting news feeds ...{Style.RESET_ALL}\n")
    news_orch.start()

    async def tech_refresh_loop():
        while True:
            await asyncio.sleep(args.refresh)
            loop = asyncio.get_event_loop()
            for t in args.tickers:
                sig = await loop.run_in_executor(None, engine.analyse, t)
                if sig:
                    tech_cache[t] = sig
            print(f"\n{Fore.CYAN}--- Technical refresh ---{Style.RESET_ALL}")
            for t in args.tickers:
                if t in tech_cache:
                    fused = fusion.fuse(tech_cache.get(t), t)
                    _print_fused(fused)

    async def news_loop():
        async for item in news_orch.stream():
            _print_news(item)
            fusion.ingest_news(item)
            relevant = tickers_set & set(item.tickers)
            for t in relevant:
                tech  = tech_cache.get(t)
                fused = fusion.fuse(tech, t)
                print(f"\n{Fore.YELLOW}  -> Signal update for {t}:{Style.RESET_ALL}")
                _print_fused(fused)

    await asyncio.gather(tech_refresh_loop(), news_loop())


# ── entry ─────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    # Resolve tickers from flags
    if args.scan_all:
        args.tickers = get_all_tickers()
    elif args.sector:
        args.tickers = get_by_sectors(args.sector)

    # Web mode
    if args.web:
        from app import app
        print(f"\n{Fore.CYAN}Starting web dashboard on http://localhost:5000{Style.RESET_ALL}\n")
        app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
        return

    try:
        if args.mode == "static":
            run_static(args)
        else:
            asyncio.run(run_live(args))
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Stopped.{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
