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
        return jsonify({"results": search_tickers(q)})
    return jsonify({"sectors": NSE_STOCKS, "sector_list": SECTOR_LIST})


@app.route("/api/trade", methods=["POST"])
def api_trade():
    data = request.get_json(force=True)
    ticker = data.get("ticker", "")
    action = data.get("action", "BUY")

    if not ticker:
        return jsonify({"error": "No ticker specified"}), 400

    # Get current price
    sig = engine.analyse(ticker)
    if not sig:
        return jsonify({"error": f"Could not fetch data for {ticker}"}), 404

    quantity, stop_loss, take_profit = sizer.calculate(sig)

    order = TradeOrder(
        ticker=ticker,
        action=action,
        quantity=quantity,
        price=sig.last_price,
        stop_loss=stop_loss if action == "BUY" else 0,
        take_profit=take_profit if action == "BUY" else 0,
        paper=True,
        reason=f"Manual {action} from web UI",
    )
    broker.place_order(order)
    sse_publish({"type": "trade_update", "order": order.to_dict()})
    return jsonify({"order": order.to_dict()})


@app.route("/api/positions")
def api_positions():
    positions = [p.to_dict() for p in broker.get_positions()]
    summary = trader.get_portfolio_summary()
    return jsonify({"positions": positions, "summary": summary})


@app.route("/api/journal")
def api_journal():
    journal = trader.get_trade_journal()
    return jsonify({"journal": journal})


@app.route("/api/thresholds")
def api_thresholds():
    return jsonify(THRESHOLDS)


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
    print("=" * 50)
    print(" Stock Analysis Web Dashboard")
    print(" Open http://localhost:5000 in your browser")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
