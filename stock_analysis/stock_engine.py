"""
Stock Analysis Engine
---------------------
Fetches OHLCV data and computes a suite of technical indicators,
then generates a composite BUY / HOLD / SELL signal with confidence score.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional
import warnings
warnings.filterwarnings("ignore")


# ── helpers ──────────────────────────────────────────────────────────────────

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

    def summary(self) -> str:
        arrow = {"BUY": "▲", "HOLD": "●", "SELL": "▼"}.get(self.signal, "?")
        return (
            f"[{self.ticker}] ${self.last_price:.2f}  "
            f"{arrow} {self.signal}  confidence={self.confidence:.1f}%  "
            f"score={self.score:+.3f}"
        )


# ── main engine ───────────────────────────────────────────────────────────────

class StockEngine:
    """Download data and compute signals for one or more tickers."""

    def __init__(self, period: str = "6mo", interval: str = "1d"):
        self.period   = period
        self.interval = interval

    # ── public ───────────────────────────────────────────────────────────────

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

    # ── private ──────────────────────────────────────────────────────────────

    def _fetch(self, ticker: str) -> Optional[pd.DataFrame]:
        try:
            df = yf.download(ticker, period=self.period,
                             interval=self.interval, progress=False,
                             auto_adjust=True)
            if df.empty:
                return None
            # flatten multi-index if present
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

        # Latest values
        p   = float(close.iloc[-1])
        r   = float(rsi.iloc[-1])
        mk  = float(macd.iloc[-1])
        ms  = float(macd_sig.iloc[-1])
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

        # ── scoring sub-signals (each returns value in [-1, +1]) ────────────
        scores = {}

        # RSI: oversold → bullish, overbought → bearish
        if   r < 30:  scores["rsi"] = +1.0
        elif r < 45:  scores["rsi"] = +0.4
        elif r > 70:  scores["rsi"] = -1.0
        elif r > 55:  scores["rsi"] = -0.4
        else:         scores["rsi"] = 0.0

        # MACD crossover
        prev_hist = float(macd_hist.iloc[-2]) if len(macd_hist) > 1 else 0
        if mh > 0 and prev_hist <= 0:   scores["macd"] = +1.0   # fresh bullish cross
        elif mh > 0:                     scores["macd"] = +0.5
        elif mh < 0 and prev_hist >= 0: scores["macd"] = -1.0   # fresh bearish cross
        else:                            scores["macd"] = -0.5

        # Bollinger %B: near lower band → bullish
        scores["bollinger"] = np.clip(1 - 2 * pb, -1, 1)

        # Stochastic
        if   sk < 20 and sk > sd: scores["stoch"] = +1.0
        elif sk < 20:              scores["stoch"] = +0.5
        elif sk > 80 and sk < sd: scores["stoch"] = -1.0
        elif sk > 80:              scores["stoch"] = -0.5
        else:                      scores["stoch"] = 0.0

        # EMA trend alignment  (20 > 50 > 200 = fully bullish)
        trend_score = 0.0
        if e20 > e50:  trend_score += 0.5
        if e50 > e200: trend_score += 0.5
        if e20 < e50:  trend_score -= 0.5
        if e50 < e200: trend_score -= 0.5
        scores["ema_trend"] = trend_score

        # Price vs VWAP
        scores["vwap"] = np.clip((p - vw) / (vw + 1e-9) * 20, -1, 1)

        # Volume surge confirms direction
        vol_multiplier = np.clip(vol_ratio - 1, 0, 2) * 0.25
        direction      = np.sign(sum(scores.values()))
        scores["volume"] = direction * vol_multiplier

        # ── composite ───────────────────────────────────────────────────────
        weights = {
            "rsi": 0.20, "macd": 0.25, "bollinger": 0.15,
            "stoch": 0.15, "ema_trend": 0.15, "vwap": 0.05, "volume": 0.05,
        }
        composite = sum(weights[k] * v for k, v in scores.items())
        composite  = float(np.clip(composite, -1, 1))

        # ── signal label ────────────────────────────────────────────────────
        if   composite >  0.25: signal = "BUY"
        elif composite < -0.25: signal = "SELL"
        else:                   signal = "HOLD"

        confidence = abs(composite) * 100

        notes = []
        if r < 30:  notes.append("RSI oversold")
        if r > 70:  notes.append("RSI overbought")
        if mh > 0 and prev_hist <= 0: notes.append("MACD bullish crossover")
        if mh < 0 and prev_hist >= 0: notes.append("MACD bearish crossover")
        if vol_ratio > 2:             notes.append(f"Volume surge ×{vol_ratio:.1f}")
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
        )
