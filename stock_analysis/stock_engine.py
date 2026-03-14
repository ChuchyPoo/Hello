"""
Stock Analysis Engine
---------------------
Fetches OHLCV data and computes a suite of technical indicators,
then generates a composite BUY / HOLD / SELL signal with confidence score
and detailed human-readable reasoning for every decision.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
import warnings
warnings.filterwarnings("ignore")


# ── helpers (importable by historical.py) ─────────────────────────────────────

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _macd(close: pd.Series):
    fast, slow, signal = 12, 26, 9
    ema_fast   = _ema(close, fast)
    ema_slow   = _ema(close, slow)
    macd_line  = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram

def _bollinger(close: pd.Series, window: int = 20, std_dev: float = 2.0):
    sma   = close.rolling(window).mean()
    sigma = close.rolling(window).std()
    upper = sma + std_dev * sigma
    lower = sma - std_dev * sigma
    pct_b = (close - lower) / (upper - lower + 1e-9)
    return upper, sma, lower, pct_b

def _atr(high, low, close, period: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def _vwap(df: pd.DataFrame) -> pd.Series:
    typical = (df["High"] + df["Low"] + df["Close"]) / 3
    return (typical * df["Volume"]).cumsum() / df["Volume"].cumsum()

def _stochastic(high, low, close, k=14, d=3):
    low_k  = low.rolling(k).min()
    high_k = high.rolling(k).max()
    pct_k  = 100 * (close - low_k) / (high_k - low_k + 1e-9)
    pct_d  = pct_k.rolling(d).mean()
    return pct_k, pct_d


# ══════════════════════════════════════════════════════════════════════════════
#  THRESHOLDS — all decision boundaries documented in one place
# ══════════════════════════════════════════════════════════════════════════════

THRESHOLDS = {
    # ── Final signal thresholds (composite score -1 to +1) ────────────────
    "BUY_THRESHOLD":          +0.25,   # composite > +0.25  →  BUY
    "SELL_THRESHOLD":         -0.25,   # composite < -0.25  →  SELL
    # anything between -0.25 and +0.25 is HOLD

    # ── RSI (0-100) ──────────────────────────────────────────────────────
    "RSI_STRONG_OVERSOLD":     30,     # RSI < 30  →  strong buy signal (+1.0)
    "RSI_MILD_OVERSOLD":       45,     # RSI 30-45 →  mild buy signal  (+0.4)
    "RSI_STRONG_OVERBOUGHT":   70,     # RSI > 70  →  strong sell signal (-1.0)
    "RSI_MILD_OVERBOUGHT":     55,     # RSI 55-70 →  mild sell signal  (-0.4)

    # ── Stochastic (0-100) ───────────────────────────────────────────────
    "STOCH_OVERSOLD":          20,     # %K < 20 → oversold zone
    "STOCH_OVERBOUGHT":        80,     # %K > 80 → overbought zone

    # ── Volume ───────────────────────────────────────────────────────────
    "VOLUME_SURGE":            2.0,    # volume > 2x avg → notable surge

    # ── Composite weights ────────────────────────────────────────────────
    "W_RSI":       0.20,
    "W_MACD":      0.25,
    "W_BOLLINGER": 0.15,
    "W_STOCH":     0.15,
    "W_EMA_TREND": 0.15,
    "W_VWAP":      0.05,
    "W_VOLUME":    0.05,
}


# ── result dataclass ──────────────────────────────────────────────────────────

@dataclass
class StockSignal:
    ticker:        str
    last_price:    float
    signal:        str          # BUY | HOLD | SELL
    confidence:    float        # 0-100
    score:         float        # raw composite score -1..+1
    indicators:    dict = field(default_factory=dict)
    notes:         list = field(default_factory=list)
    reasoning:     list = field(default_factory=list)
    sub_scores:    dict = field(default_factory=dict)
    price_history: Optional[pd.DataFrame] = field(default=None, repr=False)

    def summary(self) -> str:
        arrow = {"BUY": "▲", "HOLD": "●", "SELL": "▼"}.get(self.signal, "?")
        return (
            f"[{self.ticker}] ₹{self.last_price:.2f}  "
            f"{arrow} {self.signal}  confidence={self.confidence:.1f}%  "
            f"score={self.score:+.3f}"
        )

    def full_reasoning(self) -> str:
        lines = [f"--- Reasoning for {self.ticker} -> {self.signal} ---"]
        for r in self.reasoning:
            lines.append(f"  * {r}")
        lines.append(f"  => Composite score: {self.score:+.3f}  "
                     f"(BUY > +{THRESHOLDS['BUY_THRESHOLD']}, "
                     f"SELL < {THRESHOLDS['SELL_THRESHOLD']}, "
                     f"else HOLD)")
        lines.append(f"  => Confidence: {self.confidence:.1f}%")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """JSON-safe dict (excludes price_history DataFrame)."""
        price_data = None
        if self.price_history is not None and not self.price_history.empty:
            df = self.price_history
            price_data = {
                "dates": [d.strftime("%Y-%m-%d") for d in df.index],
                "open":  df["Open"].round(2).tolist(),
                "high":  df["High"].round(2).tolist(),
                "low":   df["Low"].round(2).tolist(),
                "close": df["Close"].round(2).tolist(),
                "volume": df["Volume"].tolist(),
            }
        return {
            "ticker":       self.ticker,
            "last_price":   round(self.last_price, 2),
            "signal":       self.signal,
            "confidence":   round(self.confidence, 1),
            "score":        round(self.score, 3),
            "indicators":   self.indicators,
            "notes":        self.notes,
            "reasoning":    self.reasoning,
            "sub_scores":   {k: round(v, 3) for k, v in self.sub_scores.items()},
            "price_data":   price_data,
        }


# ── main engine ───────────────────────────────────────────────────────────────

class StockEngine:
    """Download data and compute signals for one or more tickers."""

    def __init__(self, period: str = "6mo", interval: str = "1d"):
        self.period   = period
        self.interval = interval

    def analyse(self, ticker: str) -> Optional[StockSignal]:
        df = self._fetch(ticker)
        if df is None or len(df) < 30:
            return None
        return self._compute_signal(ticker, df)

    def analyse_many(self, tickers: list[str]) -> list[StockSignal]:
        results = []
        for t in tickers:
            sig = self.analyse(t)
            if sig:
                results.append(sig)
        results.sort(key=lambda s: s.score, reverse=True)
        return results

    def _fetch(self, ticker: str) -> Optional[pd.DataFrame]:
        try:
            df = yf.download(ticker, period=self.period,
                             interval=self.interval, progress=False,
                             auto_adjust=True)
            if df.empty:
                return None
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
        except Exception as e:
            print(f"  [fetch error] {ticker}: {e}")
            return None

    def _compute_signal(self, ticker: str, df: pd.DataFrame) -> StockSignal:
        close  = df["Close"]
        high   = df["High"]
        low    = df["Low"]
        volume = df["Volume"]
        T = THRESHOLDS

        # ── indicators ──────────────────────────────────────────────────────
        rsi              = _rsi(close)
        macd, macd_sig, macd_hist = _macd(close)
        bb_up, bb_mid, bb_low, pct_b = _bollinger(close)
        atr              = _atr(high, low, close)
        vwap             = _vwap(df)
        stoch_k, stoch_d = _stochastic(high, low, close)
        ema20            = _ema(close, 20)
        ema50            = _ema(close, 50)
        ema200           = _ema(close, 200)

        p   = float(close.iloc[-1])
        r   = float(rsi.iloc[-1])
        mh  = float(macd_hist.iloc[-1])
        pb  = float(pct_b.iloc[-1])
        sk  = float(stoch_k.iloc[-1])
        sd  = float(stoch_d.iloc[-1])
        e20 = float(ema20.iloc[-1])
        e50 = float(ema50.iloc[-1])
        e200= float(ema200.iloc[-1])
        vw  = float(vwap.iloc[-1])
        vol_avg = float(volume.rolling(20).mean().iloc[-1])
        vol_now = float(volume.iloc[-1])
        vol_ratio = vol_now / (vol_avg + 1e-9)

        scores   = {}
        reasoning = []

        # ── RSI ─────────────────────────────────────────────────────────────
        if r < T["RSI_STRONG_OVERSOLD"]:
            scores["rsi"] = +1.0
            reasoning.append(
                f"RSI = {r:.1f} (below {T['RSI_STRONG_OVERSOLD']}) -> "
                f"STRONGLY OVERSOLD. Historically stocks bounce back from "
                f"these levels. Strong buy signal. "
                f"[weight: {T['W_RSI']:.0%}, sub-score: +1.0]"
            )
        elif r < T["RSI_MILD_OVERSOLD"]:
            scores["rsi"] = +0.4
            reasoning.append(
                f"RSI = {r:.1f} ({T['RSI_STRONG_OVERSOLD']}-"
                f"{T['RSI_MILD_OVERSOLD']}) -> mildly oversold. Selling "
                f"pressure fading, potential reversal. "
                f"[weight: {T['W_RSI']:.0%}, sub-score: +0.4]"
            )
        elif r > T["RSI_STRONG_OVERBOUGHT"]:
            scores["rsi"] = -1.0
            reasoning.append(
                f"RSI = {r:.1f} (above {T['RSI_STRONG_OVERBOUGHT']}) -> "
                f"STRONGLY OVERBOUGHT. Stock overextended, pullback likely. "
                f"[weight: {T['W_RSI']:.0%}, sub-score: -1.0]"
            )
        elif r > T["RSI_MILD_OVERBOUGHT"]:
            scores["rsi"] = -0.4
            reasoning.append(
                f"RSI = {r:.1f} ({T['RSI_MILD_OVERBOUGHT']}-"
                f"{T['RSI_STRONG_OVERBOUGHT']}) -> trending overbought. "
                f"Momentum fading. "
                f"[weight: {T['W_RSI']:.0%}, sub-score: -0.4]"
            )
        else:
            scores["rsi"] = 0.0
            reasoning.append(
                f"RSI = {r:.1f} (neutral {T['RSI_MILD_OVERSOLD']}-"
                f"{T['RSI_MILD_OVERBOUGHT']}) -> no directional bias. "
                f"[weight: {T['W_RSI']:.0%}, sub-score: 0.0]"
            )

        # ── MACD ────────────────────────────────────────────────────────────
        prev_hist = float(macd_hist.iloc[-2]) if len(macd_hist) > 1 else 0
        if mh > 0 and prev_hist <= 0:
            scores["macd"] = +1.0
            reasoning.append(
                f"MACD histogram crossed above zero ({prev_hist:.4f} -> "
                f"{mh:.4f}) -> FRESH BULLISH CROSSOVER. Short-term trend "
                f"accelerating above long-term. Reliable buy signal. "
                f"[weight: {T['W_MACD']:.0%}, sub-score: +1.0]"
            )
        elif mh > 0:
            scores["macd"] = +0.5
            reasoning.append(
                f"MACD histogram positive ({mh:.4f}) -> bullish momentum "
                f"continues. [weight: {T['W_MACD']:.0%}, sub-score: +0.5]"
            )
        elif mh < 0 and prev_hist >= 0:
            scores["macd"] = -1.0
            reasoning.append(
                f"MACD histogram crossed below zero ({prev_hist:.4f} -> "
                f"{mh:.4f}) -> FRESH BEARISH CROSSOVER. Momentum flipped "
                f"negative. Strong sell signal. "
                f"[weight: {T['W_MACD']:.0%}, sub-score: -1.0]"
            )
        else:
            scores["macd"] = -0.5
            reasoning.append(
                f"MACD histogram negative ({mh:.4f}) -> bearish momentum "
                f"continues. [weight: {T['W_MACD']:.0%}, sub-score: -0.5]"
            )

        # ── Bollinger Bands ─────────────────────────────────────────────────
        bb_score = float(np.clip(1 - 2 * pb, -1, 1))
        scores["bollinger"] = bb_score
        if pb < 0.2:
            reasoning.append(
                f"Bollinger %B = {pb:.3f} -> near LOWER band. Statistically "
                f"cheap, mean reversion likely. "
                f"[weight: {T['W_BOLLINGER']:.0%}, sub-score: {bb_score:+.3f}]"
            )
        elif pb > 0.8:
            reasoning.append(
                f"Bollinger %B = {pb:.3f} -> near UPPER band. Stretched to "
                f"upside, may pull back. "
                f"[weight: {T['W_BOLLINGER']:.0%}, sub-score: {bb_score:+.3f}]"
            )
        else:
            reasoning.append(
                f"Bollinger %B = {pb:.3f} -> within bands, no extreme "
                f"pressure. [weight: {T['W_BOLLINGER']:.0%}, sub-score: {bb_score:+.3f}]"
            )

        # ── Stochastic ──────────────────────────────────────────────────────
        if sk < T["STOCH_OVERSOLD"] and sk > sd:
            scores["stoch"] = +1.0
            reasoning.append(
                f"Stochastic %K={sk:.1f}, %D={sd:.1f} -> oversold + %K "
                f"crossing above %D. Classic buy signal. "
                f"[weight: {T['W_STOCH']:.0%}, sub-score: +1.0]"
            )
        elif sk < T["STOCH_OVERSOLD"]:
            scores["stoch"] = +0.5
            reasoning.append(
                f"Stochastic %K={sk:.1f} -> oversold (below {T['STOCH_OVERSOLD']}), "
                f"waiting for crossover confirmation. "
                f"[weight: {T['W_STOCH']:.0%}, sub-score: +0.5]"
            )
        elif sk > T["STOCH_OVERBOUGHT"] and sk < sd:
            scores["stoch"] = -1.0
            reasoning.append(
                f"Stochastic %K={sk:.1f}, %D={sd:.1f} -> overbought + %K "
                f"crossing below %D. Classic sell signal. "
                f"[weight: {T['W_STOCH']:.0%}, sub-score: -1.0]"
            )
        elif sk > T["STOCH_OVERBOUGHT"]:
            scores["stoch"] = -0.5
            reasoning.append(
                f"Stochastic %K={sk:.1f} -> overbought (above {T['STOCH_OVERBOUGHT']}), "
                f"no bearish cross yet. "
                f"[weight: {T['W_STOCH']:.0%}, sub-score: -0.5]"
            )
        else:
            scores["stoch"] = 0.0
            reasoning.append(
                f"Stochastic %K={sk:.1f} -> neutral zone. "
                f"[weight: {T['W_STOCH']:.0%}, sub-score: 0.0]"
            )

        # ── EMA trend alignment ─────────────────────────────────────────────
        trend_score = 0.0
        trend_parts = []
        if e20 > e50:
            trend_score += 0.5
            trend_parts.append("20-EMA > 50-EMA (short-term uptrend)")
        if e50 > e200:
            trend_score += 0.5
            trend_parts.append("50-EMA > 200-EMA (long-term uptrend)")
        if e20 < e50:
            trend_score -= 0.5
            trend_parts.append("20-EMA < 50-EMA (short-term downtrend)")
        if e50 < e200:
            trend_score -= 0.5
            trend_parts.append("50-EMA < 200-EMA (death cross)")
        scores["ema_trend"] = trend_score
        reasoning.append(
            f"EMA alignment: {'; '.join(trend_parts)}. "
            f"EMA20={e20:.2f}, EMA50={e50:.2f}, EMA200={e200:.2f}. "
            f"[weight: {T['W_EMA_TREND']:.0%}, sub-score: {trend_score:+.1f}]"
        )

        # ── VWAP ────────────────────────────────────────────────────────────
        vwap_score = float(np.clip((p - vw) / (vw + 1e-9) * 20, -1, 1))
        scores["vwap"] = vwap_score
        if p > vw:
            reasoning.append(
                f"Price {p:.2f} ABOVE VWAP {vw:.2f} -> buyers in control. "
                f"[weight: {T['W_VWAP']:.0%}, sub-score: {vwap_score:+.3f}]"
            )
        else:
            reasoning.append(
                f"Price {p:.2f} BELOW VWAP {vw:.2f} -> sellers in control. "
                f"[weight: {T['W_VWAP']:.0%}, sub-score: {vwap_score:+.3f}]"
            )

        # ── Volume ──────────────────────────────────────────────────────────
        vol_multiplier = float(np.clip(vol_ratio - 1, 0, 2) * 0.25)
        direction      = np.sign(sum(scores.values()))
        vol_score      = float(direction * vol_multiplier)
        scores["volume"] = vol_score
        if vol_ratio > T["VOLUME_SURGE"]:
            reasoning.append(
                f"Volume {vol_ratio:.1f}x avg -> SURGE. Confirms current "
                f"direction. [weight: {T['W_VOLUME']:.0%}, sub-score: {vol_score:+.3f}]"
            )
        else:
            reasoning.append(
                f"Volume {vol_ratio:.2f}x avg -> normal. "
                f"[weight: {T['W_VOLUME']:.0%}, sub-score: {vol_score:+.3f}]"
            )

        # ── composite ───────────────────────────────────────────────────────
        weights = {
            "rsi": T["W_RSI"], "macd": T["W_MACD"],
            "bollinger": T["W_BOLLINGER"], "stoch": T["W_STOCH"],
            "ema_trend": T["W_EMA_TREND"], "vwap": T["W_VWAP"],
            "volume": T["W_VOLUME"],
        }
        composite = sum(weights[k] * v for k, v in scores.items())
        composite  = float(np.clip(composite, -1, 1))

        if   composite > T["BUY_THRESHOLD"]:  signal = "BUY"
        elif composite < T["SELL_THRESHOLD"]: signal = "SELL"
        else:                                  signal = "HOLD"

        confidence = abs(composite) * 100

        bullish_count = sum(1 for v in scores.values() if v > 0)
        bearish_count = sum(1 for v in scores.values() if v < 0)
        neutral_count = sum(1 for v in scores.values() if v == 0)
        reasoning.append(
            f"DECISION: {bullish_count} bullish, {bearish_count} bearish, "
            f"{neutral_count} neutral. Score = {composite:+.3f}. "
            f"BUY > +{T['BUY_THRESHOLD']}, SELL < {T['SELL_THRESHOLD']}, "
            f"else HOLD -> {signal} ({confidence:.1f}% confidence)."
        )

        notes = []
        if r < T["RSI_STRONG_OVERSOLD"]:  notes.append("RSI oversold")
        if r > T["RSI_STRONG_OVERBOUGHT"]: notes.append("RSI overbought")
        if mh > 0 and prev_hist <= 0: notes.append("MACD bullish crossover")
        if mh < 0 and prev_hist >= 0: notes.append("MACD bearish crossover")
        if vol_ratio > T["VOLUME_SURGE"]: notes.append(f"Volume surge x{vol_ratio:.1f}")
        if p > e200: notes.append("Price above 200-EMA")
        if p < e200: notes.append("Price below 200-EMA")

        return StockSignal(
            ticker=ticker,
            last_price=p,
            signal=signal,
            confidence=confidence,
            score=composite,
            indicators={
                "rsi": round(r, 2),
                "macd_hist": round(mh, 4),
                "pct_b": round(pb, 3),
                "stoch_k": round(sk, 2),
                "stoch_d": round(sd, 2),
                "ema20": round(e20, 2),
                "ema50": round(e50, 2),
                "ema200": round(e200, 2),
                "vwap": round(vw, 2),
                "vol_ratio": round(vol_ratio, 2),
                "atr": round(float(atr.iloc[-1]), 4),
                **{f"sub_{k}": round(v, 3) for k, v in scores.items()},
            },
            notes=notes,
            reasoning=reasoning,
            sub_scores=dict(scores),
            price_history=df,
        )
