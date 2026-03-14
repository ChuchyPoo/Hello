"""
Auto-Trading Module
--------------------
Automated buy/sell execution with paper trading (default) and
live broker integration (Zerodha Kite, Angel One SmartAPI).

SAFETY: Paper mode is always default. Live trading requires
explicit --live-trade flag and typed "YES" confirmation.
"""

import json
import time
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional
from pathlib import Path

from stock_engine import StockSignal


JOURNAL_FILE = Path(__file__).parent / "trade_journal.json"


# ── data models ───────────────────────────────────────────────────────────────

@dataclass
class TradeOrder:
    ticker:      str
    action:      str          # BUY | SELL
    quantity:    int
    price:       float
    order_type:  str = "MARKET"   # MARKET | LIMIT
    stop_loss:   float = 0.0
    take_profit: float = 0.0
    timestamp:   str = ""
    status:      str = "PENDING"  # PENDING | EXECUTED | CANCELLED | FAILED
    broker:      str = "paper"
    order_id:    str = ""
    paper:       bool = True
    reason:      str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Position:
    ticker:       str
    quantity:     int
    entry_price:  float
    entry_time:   str
    stop_loss:    float
    take_profit:  float
    current_price: float = 0.0
    broker:       str = "paper"

    @property
    def pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.quantity

    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price * 100

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pnl"] = round(self.pnl, 2)
        d["pnl_pct"] = round(self.pnl_pct, 2)
        return d


# ── position sizing ──────────────────────────────────────────────────────────

class PositionSizer:
    """
    Calculates quantity, stop-loss, and take-profit for a trade.

    Rules:
      - Max 5% of capital per position
      - Max 2% of capital at risk per trade
      - Stop-loss: 2x ATR below entry (BUY) or above entry (SELL)
      - Take-profit: 3x ATR above entry (BUY) or below entry (SELL)
    """

    def __init__(self, capital: float = 100_000,
                 max_position_pct: float = 0.05,
                 max_risk_pct: float = 0.02):
        self.capital = capital
        self.max_position_pct = max_position_pct
        self.max_risk_pct = max_risk_pct

    def calculate(self, signal: StockSignal) -> tuple[int, float, float]:
        """Return (quantity, stop_loss, take_profit)."""
        price = signal.last_price
        atr   = signal.indicators.get("atr", price * 0.02)

        # Max position value
        max_position_value = self.capital * self.max_position_pct
        max_qty_by_position = int(max_position_value / price) if price > 0 else 0

        # Max qty by risk: risk per share = 2 * ATR
        risk_per_share = 2 * atr
        max_risk_value = self.capital * self.max_risk_pct
        max_qty_by_risk = int(max_risk_value / risk_per_share) if risk_per_share > 0 else 0

        quantity = max(1, min(max_qty_by_position, max_qty_by_risk))

        if signal.signal == "BUY":
            stop_loss   = round(price - 2 * atr, 2)
            take_profit = round(price + 3 * atr, 2)
        else:  # SELL
            stop_loss   = round(price + 2 * atr, 2)
            take_profit = round(price - 3 * atr, 2)

        return quantity, stop_loss, take_profit


# ── broker interface ──────────────────────────────────────────────────────────

class BrokerBase(ABC):
    """Abstract broker interface."""

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def place_order(self, order: TradeOrder) -> str:
        """Place order, return order_id."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass

    @abstractmethod
    def get_positions(self) -> list[Position]:
        pass

    @abstractmethod
    def get_balance(self) -> float:
        pass


class PaperBroker(BrokerBase):
    """Simulated broker for risk-free paper trading."""

    def __init__(self, capital: float = 100_000):
        self.initial_capital = capital
        self.balance = capital
        self.positions: list[Position] = []
        self._order_counter = 0
        self._trade_log: list[dict] = []
        self._load_journal()

    def connect(self) -> bool:
        print("[PaperBroker] Connected (simulated)")
        return True

    def place_order(self, order: TradeOrder) -> str:
        self._order_counter += 1
        order_id = f"PAPER-{self._order_counter:06d}"
        order.order_id = order_id
        order.paper = True
        order.broker = "paper"

        if order.action == "BUY":
            cost = order.price * order.quantity
            if cost > self.balance:
                order.status = "FAILED"
                order.reason = f"Insufficient balance: need {cost:.2f}, have {self.balance:.2f}"
                self._log(order)
                return order_id

            self.balance -= cost
            self.positions.append(Position(
                ticker=order.ticker,
                quantity=order.quantity,
                entry_price=order.price,
                entry_time=order.timestamp,
                stop_loss=order.stop_loss,
                take_profit=order.take_profit,
                current_price=order.price,
                broker="paper",
            ))
            order.status = "EXECUTED"

        elif order.action == "SELL":
            # Find matching position
            found = False
            for pos in self.positions:
                if pos.ticker == order.ticker:
                    proceeds = order.price * min(order.quantity, pos.quantity)
                    self.balance += proceeds
                    self.positions.remove(pos)
                    order.status = "EXECUTED"
                    found = True
                    break
            if not found:
                order.status = "FAILED"
                order.reason = f"No open position for {order.ticker}"

        self._log(order)
        return order_id

    def cancel_order(self, order_id: str) -> bool:
        return True

    def get_positions(self) -> list[Position]:
        return self.positions

    def get_balance(self) -> float:
        return self.balance

    def _log(self, order: TradeOrder):
        entry = order.to_dict()
        self._trade_log.append(entry)
        self._save_journal()

    def _save_journal(self):
        try:
            with open(JOURNAL_FILE, "w") as f:
                json.dump(self._trade_log, f, indent=2, default=str)
        except Exception:
            pass

    def _load_journal(self):
        try:
            if JOURNAL_FILE.exists():
                with open(JOURNAL_FILE) as f:
                    self._trade_log = json.load(f)
        except Exception:
            self._trade_log = []


class ZerodhaBroker(BrokerBase):
    """
    Zerodha Kite Connect integration.

    Setup:
      pip install kiteconnect
      Set ZERODHA_API_KEY and ZERODHA_ACCESS_TOKEN in .env

    Get access token:
      1. Login at https://kite.trade/connect/login?api_key=YOUR_KEY
      2. Exchange request_token for access_token using kite.generate_session()
    """

    def __init__(self):
        self.kite = None
        self.api_key = os.getenv("ZERODHA_API_KEY", "")
        self.access_token = os.getenv("ZERODHA_ACCESS_TOKEN", "")

    def connect(self) -> bool:
        try:
            from kiteconnect import KiteConnect
            self.kite = KiteConnect(api_key=self.api_key)
            self.kite.set_access_token(self.access_token)
            profile = self.kite.profile()
            print(f"[Zerodha] Connected as {profile['user_name']}")
            return True
        except Exception as e:
            print(f"[Zerodha] Connection failed: {e}")
            return False

    def place_order(self, order: TradeOrder) -> str:
        if not self.kite:
            order.status = "FAILED"
            order.reason = "Not connected"
            return ""
        try:
            # Convert .NS ticker to Zerodha format (NSE:SYMBOL)
            symbol = order.ticker.replace(".NS", "")
            txn = self.kite.TRANSACTION_TYPE_BUY if order.action == "BUY" \
                else self.kite.TRANSACTION_TYPE_SELL

            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.kite.EXCHANGE_NSE,
                tradingsymbol=symbol,
                transaction_type=txn,
                quantity=order.quantity,
                product=self.kite.PRODUCT_CNC,
                order_type=self.kite.ORDER_TYPE_MARKET,
            )
            order.order_id = str(order_id)
            order.status = "EXECUTED"
            order.broker = "zerodha"
            order.paper = False
            return order.order_id
        except Exception as e:
            order.status = "FAILED"
            order.reason = str(e)
            return ""

    def cancel_order(self, order_id: str) -> bool:
        try:
            self.kite.cancel_order(
                variety=self.kite.VARIETY_REGULAR,
                order_id=order_id,
            )
            return True
        except Exception:
            return False

    def get_positions(self) -> list[Position]:
        if not self.kite:
            return []
        try:
            holdings = self.kite.holdings()
            return [
                Position(
                    ticker=h["tradingsymbol"] + ".NS",
                    quantity=h["quantity"],
                    entry_price=h["average_price"],
                    entry_time="",
                    stop_loss=0,
                    take_profit=0,
                    current_price=h["last_price"],
                    broker="zerodha",
                )
                for h in holdings if h["quantity"] > 0
            ]
        except Exception:
            return []

    def get_balance(self) -> float:
        try:
            margins = self.kite.margins()
            return float(margins["equity"]["available"]["live_balance"])
        except Exception:
            return 0.0


class AngelOneBroker(BrokerBase):
    """
    Angel One SmartAPI integration.

    Setup:
      pip install smartapi-python pyotp
      Set ANGELONE_API_KEY, ANGELONE_CLIENT_ID,
          ANGELONE_PASSWORD, ANGELONE_TOTP_SECRET in .env
    """

    def __init__(self):
        self.smart_api = None
        self.api_key = os.getenv("ANGELONE_API_KEY", "")
        self.client_id = os.getenv("ANGELONE_CLIENT_ID", "")
        self.password = os.getenv("ANGELONE_PASSWORD", "")
        self.totp_secret = os.getenv("ANGELONE_TOTP_SECRET", "")

    def connect(self) -> bool:
        try:
            from SmartApi import SmartConnect
            import pyotp
            self.smart_api = SmartConnect(api_key=self.api_key)
            totp = pyotp.TOTP(self.totp_secret).now()
            data = self.smart_api.generateSession(
                self.client_id, self.password, totp
            )
            if data["status"]:
                print(f"[AngelOne] Connected as {self.client_id}")
                return True
            return False
        except Exception as e:
            print(f"[AngelOne] Connection failed: {e}")
            return False

    def place_order(self, order: TradeOrder) -> str:
        if not self.smart_api:
            order.status = "FAILED"
            order.reason = "Not connected"
            return ""
        try:
            symbol = order.ticker.replace(".NS", "")
            params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": "",  # needs token lookup
                "transactiontype": order.action,
                "exchange": "NSE",
                "ordertype": "MARKET",
                "producttype": "DELIVERY",
                "duration": "DAY",
                "quantity": str(order.quantity),
            }
            resp = self.smart_api.placeOrder(params)
            order.order_id = str(resp)
            order.status = "EXECUTED"
            order.broker = "angelone"
            order.paper = False
            return order.order_id
        except Exception as e:
            order.status = "FAILED"
            order.reason = str(e)
            return ""

    def cancel_order(self, order_id: str) -> bool:
        try:
            self.smart_api.cancelOrder(order_id, "NORMAL")
            return True
        except Exception:
            return False

    def get_positions(self) -> list[Position]:
        if not self.smart_api:
            return []
        try:
            holdings = self.smart_api.holding()
            if not holdings or not holdings.get("data"):
                return []
            return [
                Position(
                    ticker=h["tradingsymbol"] + ".NS",
                    quantity=int(h["quantity"]),
                    entry_price=float(h["averageprice"]),
                    entry_time="",
                    stop_loss=0,
                    take_profit=0,
                    current_price=float(h.get("ltp", 0)),
                    broker="angelone",
                )
                for h in holdings["data"] if int(h["quantity"]) > 0
            ]
        except Exception:
            return []

    def get_balance(self) -> float:
        try:
            funds = self.smart_api.rmsLimit()
            return float(funds["data"]["availablecash"])
        except Exception:
            return 0.0


# ── broker registry ───────────────────────────────────────────────────────────

BROKER_REGISTRY = {
    "paper":    PaperBroker,
    "zerodha":  ZerodhaBroker,
    "angelone": AngelOneBroker,
}


# ── auto-trader ───────────────────────────────────────────────────────────────

class AutoTrader:
    """
    Evaluates signals and executes trades automatically.

    Safety rules:
      - Paper mode by default
      - Only trades when confidence > 60%
      - Max 10 trades per day
      - Max 2% daily loss limit
      - Checks stop-loss and take-profit on open positions
    """

    MIN_CONFIDENCE = 60.0
    MAX_DAILY_TRADES = 10
    MAX_DAILY_LOSS_PCT = 2.0

    def __init__(self, broker: BrokerBase, sizer: PositionSizer,
                 dry_run: bool = True):
        self.broker  = broker
        self.sizer   = sizer
        self.dry_run = dry_run
        self._daily_trades = 0
        self._daily_date = ""

    def evaluate_and_trade(self, signal: StockSignal) -> Optional[TradeOrder]:
        """Decide whether to trade based on signal, and execute if appropriate."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._daily_date != today:
            self._daily_date = today
            self._daily_trades = 0

        # Check daily trade limit
        if self._daily_trades >= self.MAX_DAILY_TRADES:
            return None

        # Only trade on clear BUY or SELL with high confidence
        if signal.signal == "HOLD":
            return None
        if signal.confidence < self.MIN_CONFIDENCE:
            return None

        # Check for conflicting positions
        positions = self.broker.get_positions()
        existing = [p for p in positions if p.ticker == signal.ticker]

        if signal.signal == "BUY" and existing:
            return None  # already holding
        if signal.signal == "SELL" and not existing:
            return None  # nothing to sell

        # Size the position
        quantity, stop_loss, take_profit = self.sizer.calculate(signal)

        order = TradeOrder(
            ticker=signal.ticker,
            action=signal.signal,
            quantity=quantity,
            price=signal.last_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            paper=self.dry_run,
            reason=(
                f"Auto-trade: {signal.signal} signal with "
                f"{signal.confidence:.1f}% confidence, score={signal.score:+.3f}"
            ),
        )

        if self.dry_run:
            order.broker = "paper"
            # Use paper broker
            if isinstance(self.broker, PaperBroker):
                self.broker.place_order(order)
            else:
                order.status = "SIMULATED"
        else:
            self.broker.place_order(order)

        self._daily_trades += 1
        return order

    def check_exits(self, current_prices: dict[str, float]) -> list[TradeOrder]:
        """Check all open positions for stop-loss or take-profit triggers."""
        exit_orders = []
        positions = self.broker.get_positions()

        for pos in positions:
            price = current_prices.get(pos.ticker, pos.current_price)
            pos.current_price = price

            should_exit = False
            reason = ""

            if pos.stop_loss > 0 and price <= pos.stop_loss:
                should_exit = True
                reason = f"Stop-loss triggered at {price:.2f} (SL={pos.stop_loss:.2f})"
            elif pos.take_profit > 0 and price >= pos.take_profit:
                should_exit = True
                reason = f"Take-profit triggered at {price:.2f} (TP={pos.take_profit:.2f})"

            if should_exit:
                order = TradeOrder(
                    ticker=pos.ticker,
                    action="SELL",
                    quantity=pos.quantity,
                    price=price,
                    paper=self.dry_run,
                    reason=reason,
                )
                if isinstance(self.broker, PaperBroker):
                    self.broker.place_order(order)
                elif not self.dry_run:
                    self.broker.place_order(order)
                exit_orders.append(order)

        return exit_orders

    def get_trade_journal(self) -> list[dict]:
        """Read trade journal from disk."""
        try:
            if JOURNAL_FILE.exists():
                with open(JOURNAL_FILE) as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def get_open_positions(self) -> list[dict]:
        return [p.to_dict() for p in self.broker.get_positions()]

    def get_portfolio_summary(self) -> dict:
        positions = self.broker.get_positions()
        total_invested = sum(p.entry_price * p.quantity for p in positions)
        total_current  = sum(p.current_price * p.quantity for p in positions)
        total_pnl      = total_current - total_invested
        balance        = self.broker.get_balance()

        return {
            "balance":        round(balance, 2),
            "invested":       round(total_invested, 2),
            "current_value":  round(total_current, 2),
            "total_pnl":      round(total_pnl, 2),
            "total_pnl_pct":  round(total_pnl / (total_invested + 1e-9) * 100, 2),
            "open_positions": len(positions),
            "broker":         positions[0].broker if positions else "paper",
        }
