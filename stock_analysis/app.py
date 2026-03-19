"""
Flask Web Dashboard
--------------------
Run with: python app.py
Open: http://localhost:5000
"""

import json
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template, request, jsonify, Response

from stock_engine import StockEngine, StockSignal, THRESHOLDS
from historical import HistoricalPatternMatcher, summarize_matches
from auto_trader import (
    AutoTrader, PaperBroker, PositionSizer, TradeOrder, BROKER_REGISTRY
)
from nse_stocks import (
    NSE_STOCKS, SECTOR_LIST, get_all_tickers, get_by_sector,
    get_by_sectors, search_tickers, get_stock_info
)
from google_finance import fetch_google_finance_details, search_google_finance
from markets import MARKETS, MARKET_LIST, get_market
from mutual_funds import (
    search_funds, get_fund_nav, make_mf_ticker, parse_mf_ticker,
    is_mf_ticker, POPULAR_FUNDS
)

app = Flask(__name__)

# ── shared state ──────────────────────────────────────────────────────────────

engine   = StockEngine(period="1y", interval="1d")
matcher  = HistoricalPatternMatcher()
broker   = PaperBroker(capital=100_000)
sizer    = PositionSizer(capital=100_000)
trader   = AutoTrader(broker=broker, sizer=sizer, dry_run=True)
executor = ThreadPoolExecutor(max_workers=8)

# SSE clients
sse_clients: list[queue.Queue] = []


def sse_publish(data: dict):
    for q in sse_clients[:]:
        try:
            q.put_nowait(data)
        except queue.Full:
            pass


# ── pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("dashboard.html", active="dashboard", sectors=SECTOR_LIST)

@app.route("/stock/<path:ticker>")
def stock_detail(ticker: str):
    return render_template("stock_detail.html", active="", ticker=ticker)

@app.route("/trading")
def trading():
    return render_template("trading.html", active="trading")

@app.route("/funds")
def funds():
    return render_template("funds.html", active="funds",
                           popular_funds=POPULAR_FUNDS)


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.route("/api/scan", methods=["POST"])
def api_scan():
    data = request.get_json(force=True)
    sector    = data.get("sector", "all")
    max_price = data.get("max_price", 1000)
    scan_all  = data.get("scan_all", False)

    if scan_all or sector == "all":
        tickers = get_all_tickers()
    else:
        tickers = get_by_sector(sector)

    if not tickers:
        return jsonify({"results": [], "error": "No tickers found for sector"})

    sse_publish({"type": "scan_progress", "message": f"Scanning {len(tickers)} stocks..."})

    results = []
    def analyse_one(t):
        return engine.analyse(t)

    # Parallel analysis
    futures = {executor.submit(analyse_one, t): t for t in tickers}
    done_count = 0
    for future in futures:
        try:
            sig = future.result(timeout=30)
            done_count += 1
            if done_count % 5 == 0:
                sse_publish({"type": "scan_progress",
                             "message": f"Scanned {done_count}/{len(tickers)}..."})
            if sig and sig.last_price <= max_price:
                d = sig.to_dict()
                info = get_stock_info(sig.ticker)
                d["name"] = info["name"] if info else ""
                results.append(d)
        except Exception:
            pass

    results.sort(key=lambda r: r["score"], reverse=True)
    sse_publish({"type": "scan_progress",
                 "message": f"Done! {len(results)} stocks under ₹{max_price}"})
    return jsonify({"results": results})


@app.route("/api/stock/<path:ticker>")
def api_stock(ticker: str):
    sig = engine.analyse(ticker)
    if not sig:
        return jsonify({"error": f"Could not fetch data for {ticker}"}), 404

    # Historical matches
    matches = matcher.find_matches(sig)
    summary = summarize_matches(matches)

    return jsonify({
        "signal": sig.to_dict(),
        "historical": {
            "matches": [m.to_dict() for m in matches],
            "summary": summary,
        },
        "thresholds": THRESHOLDS,
    })


@app.route("/api/stocks")
def api_stocks():
    q = request.args.get("q", "")
    if q:
        # Search local NSE database first
        local_results = search_tickers(q)
        if local_results:
            return jsonify({"results": local_results})
        # Fallback: try Google Finance search
        google_results = search_google_finance(q)
        if google_results:
            return jsonify({"results": google_results, "source": "google"})
        # Last resort: let user try directly with .NS suffix
        return jsonify({"results": [
            {"ticker": f"{q.upper()}.NS", "name": f"{q.upper()} (try direct)", "sector": "unknown"}
        ], "source": "guess"})
    return jsonify({"sectors": NSE_STOCKS, "sector_list": SECTOR_LIST})


@app.route("/api/trade", methods=["POST"])
def api_trade():
    data = request.get_json(force=True)
    ticker = data.get("ticker", "")
    action = data.get("action", "BUY")
    amount = data.get("amount", 0)  # user-specified INR amount

    if not ticker:
        return jsonify({"error": "No ticker specified"}), 400

    # Get current price
    sig = engine.analyse(ticker)
    if not sig:
        return jsonify({"error": f"Could not fetch data for {ticker}"}), 404

    price = sig.last_price

    if amount and amount > 0 and action == "BUY":
        # User specified an amount — calculate quantity from it
        quantity = max(1, int(amount / price))
        actual_cost = quantity * price
        atr = sig.indicators.get("atr", price * 0.02)
        stop_loss = round(price - 2 * atr, 2)
        take_profit = round(price + 3 * atr, 2)
    elif action == "SELL":
        # For SELL, sell all shares of this position
        positions = broker.get_positions()
        pos = next((p for p in positions if p.ticker == ticker), None)
        if not pos:
            return jsonify({"error": f"No open position for {ticker}"}), 400
        quantity = pos.quantity
        stop_loss = 0
        take_profit = 0
    else:
        # Fallback to position sizer
        quantity, stop_loss, take_profit = sizer.calculate(sig)

    order = TradeOrder(
        ticker=ticker,
        action=action,
        quantity=quantity,
        price=price,
        stop_loss=stop_loss if action == "BUY" else 0,
        take_profit=take_profit if action == "BUY" else 0,
        paper=True,
        reason=f"Manual {action} ₹{amount:,.0f}" if amount else f"Manual {action} from web UI",
    )
    broker.place_order(order)
    sse_publish({"type": "trade_update", "order": order.to_dict()})
    return jsonify({"order": order.to_dict()})


@app.route("/api/positions")
def api_positions():
    # Update current prices for all open positions
    positions = broker.get_positions()
    for pos in positions:
        try:
            if is_mf_ticker(pos.ticker):
                # Mutual fund — fetch latest NAV
                sc = parse_mf_ticker(pos.ticker)
                if sc:
                    fund = get_fund_nav(sc)
                    if fund:
                        pos.current_price = fund["nav"]
            else:
                sig = engine.analyse(pos.ticker)
                if sig:
                    pos.current_price = sig.last_price
        except Exception:
            pass
    broker._save_portfolio()

    positions_data = [p.to_dict() for p in positions]
    summary = trader.get_portfolio_summary()
    return jsonify({"positions": positions_data, "summary": summary})


@app.route("/api/journal")
def api_journal():
    journal = trader.get_trade_journal()
    return jsonify({"journal": journal})


@app.route("/api/thresholds")
def api_thresholds():
    return jsonify(THRESHOLDS)


@app.route("/api/google/<path:ticker>")
def api_google_data(ticker: str):
    """Get enriched data from Google Finance for a ticker."""
    data = fetch_google_finance_details(ticker)
    if not data:
        return jsonify({"error": f"No Google Finance data for {ticker}"}), 404
    return jsonify(data)


@app.route("/api/portfolio/reset", methods=["POST"])
def api_portfolio_reset():
    """Reset paper portfolio to starting capital."""
    broker.balance = broker.initial_capital
    broker.positions.clear()
    broker._trade_log.clear()
    broker._order_counter = 0
    broker._save_portfolio()
    broker._save_journal()
    return jsonify({"status": "reset", "balance": broker.balance})


@app.route("/api/markets")
def api_markets():
    """Return all supported markets."""
    return jsonify({"markets": MARKETS, "market_list": MARKET_LIST})


@app.route("/api/market/<market_id>/stocks")
def api_market_stocks(market_id: str):
    """Return popular stocks for a given market."""
    market = get_market(market_id)
    return jsonify({
        "market_id":  market_id,
        "market":     market,
        "popular":    market.get("popular", []),
    })


@app.route("/api/market/search")
def api_market_search():
    """Search stocks in a given market. Uses local DB for NSE, Google Finance for others."""
    q      = request.args.get("q", "").strip()
    market = request.args.get("market", "nse_india")
    if not q:
        return jsonify({"results": []})

    if market == "nse_india":
        # Local search first
        local = search_tickers(q)
        if local:
            return jsonify({"results": local})
        # Fallback to Google
        g = search_google_finance(q)
        if g:
            return jsonify({"results": g, "source": "google"})
        suffix = MARKETS["nse_india"]["suffix"]
        return jsonify({"results": [
            {"ticker": f"{q.upper()}{suffix}", "name": f"{q.upper()} (try direct)", "sector": ""}
        ]})
    else:
        # Use Google Finance search for international markets
        g = search_google_finance(q)
        mkt_info = get_market(market)
        suffix   = mkt_info.get("suffix", "")
        if g:
            return jsonify({"results": g, "source": "google"})
        # Let user try directly with the market suffix
        return jsonify({"results": [
            {"ticker": f"{q.upper()}{suffix}", "name": f"{q.upper()} (try direct)", "sector": ""}
        ]})


# ── Mutual Fund endpoints ────────────────────────────────────────────────────

@app.route("/api/mf/search")
def api_mf_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": POPULAR_FUNDS})
    results = search_funds(q)
    return jsonify({"results": results})


@app.route("/api/mf/<scheme_code>")
def api_mf_detail(scheme_code: str):
    data = get_fund_nav(scheme_code)
    if not data:
        return jsonify({"error": f"Fund {scheme_code} not found"}), 404
    return jsonify(data)


@app.route("/api/mf/buy", methods=["POST"])
def api_mf_buy():
    """Paper-buy a mutual fund.

    Body: { scheme_code, amount }
    Amount is in INR; units = floor(amount / nav).
    """
    body        = request.get_json(force=True)
    scheme_code = str(body.get("scheme_code", "")).strip()
    amount      = float(body.get("amount", 0))

    if not scheme_code:
        return jsonify({"error": "scheme_code required"}), 400
    if amount <= 0:
        return jsonify({"error": "amount must be > 0"}), 400

    fund = get_fund_nav(scheme_code)
    if not fund:
        return jsonify({"error": f"Fund {scheme_code} not found"}), 404

    nav      = fund["nav"]
    units    = max(1, int(amount / nav))
    ticker   = make_mf_ticker(scheme_code)

    order = TradeOrder(
        ticker      = ticker,
        action      = "BUY",
        quantity    = units,
        price       = nav,
        stop_loss   = 0,
        take_profit = 0,
        paper       = True,
        reason      = f"MF buy ₹{amount:,.0f} — {fund['scheme_name'][:40]}",
    )
    broker.place_order(order)
    sse_publish({"type": "trade_update", "order": order.to_dict()})
    return jsonify({
        "order":    order.to_dict(),
        "fund":     fund["scheme_name"],
        "units":    units,
        "nav":      nav,
        "nav_date": fund["nav_date"],
    })


@app.route("/api/mf/sell", methods=["POST"])
def api_mf_sell():
    """Paper-sell all units of a mutual fund position."""
    body        = request.get_json(force=True)
    scheme_code = str(body.get("scheme_code", "")).strip()
    ticker      = make_mf_ticker(scheme_code)

    positions = broker.get_positions()
    pos = next((p for p in positions if p.ticker == ticker), None)
    if not pos:
        return jsonify({"error": f"No open position for fund {scheme_code}"}), 400

    fund = get_fund_nav(scheme_code)
    nav  = fund["nav"] if fund else pos.current_price

    order = TradeOrder(
        ticker  = ticker,
        action  = "SELL",
        quantity= pos.quantity,
        price   = nav,
        paper   = True,
        reason  = f"MF sell — {fund['scheme_name'][:40] if fund else scheme_code}",
    )
    broker.place_order(order)
    sse_publish({"type": "trade_update", "order": order.to_dict()})
    return jsonify({"order": order.to_dict(), "nav": nav})


@app.route("/api/freshness", methods=["POST"])
def api_freshness():
    """Check data freshness for a list of tickers (or defaults to priority stocks).
    Returns data_date and data_age_days for each ticker.
    """
    from datetime import date
    data = request.get_json(force=True) or {}
    tickers = data.get("tickers") or [s["ticker"] for s in NSE_STOCKS.get("priority", [])]

    results = []
    def check_one(t):
        sig = engine.analyse(t)
        if sig:
            return {"ticker": t, "data_date": sig.data_date, "data_age_days": sig.to_dict()["data_age_days"]}
        return {"ticker": t, "data_date": None, "data_age_days": None}

    futures = {executor.submit(check_one, t): t for t in tickers}
    for future in futures:
        try:
            results.append(future.result(timeout=30))
        except Exception:
            pass

    today = date.today().isoformat()
    stale = [r for r in results if r["data_age_days"] is not None and r["data_age_days"] > 3]
    return jsonify({
        "checked_at": today,
        "results": results,
        "stale_count": len(stale),
        "stale_tickers": [r["ticker"] for r in stale],
    })


@app.route("/api/stream")
def api_stream():
    def generate():
        q = queue.Queue(maxsize=50)
        sse_clients.append(q)
        try:
            # Send initial heartbeat
            yield "data: {\"type\": \"connected\"}\n\n"
            while True:
                try:
                    data = q.get(timeout=30)
                    yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            if q in sse_clients:
                sse_clients.remove(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


# ── entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print("=" * 50)
    print(" Stock Analysis Web Dashboard")
    print(f" Open http://localhost:{port} in your browser")
    print("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
