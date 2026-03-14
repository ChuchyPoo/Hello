"""
Historical Pattern Matching
----------------------------
Scans a stock's own price history for past moments where technical indicators
were similar to today, then reports what happened next (1d, 5d, 10d, 20d returns).

Uses cosine similarity on a normalised feature vector of:
  [RSI, MACD_hist_sign, MACD_hist_magnitude, %B, Stoch_%K, EMA_alignment, VWAP_position, volume_ratio]
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional
from sklearn.metrics.pairwise import cosine_similarity

from stock_engine import (
    StockSignal, _rsi, _macd, _bollinger, _stochastic, _ema, _vwap, _atr, THRESHOLDS
)


FORWARD_WINDOWS = [1, 5, 10, 20]   # trading days to look ahead


@dataclass
class HistoricalMatch:
    match_date:      str         # YYYY-MM-DD
    similarity:      float       # 0.0 - 1.0
    indicators:      dict        # RSI, MACD, etc. at that point
    forward_returns: dict        # {"1d": +0.5, "5d": +2.1, ...} in %
    description:     str         # human-readable summary

    def to_dict(self) -> dict:
        return {
            "match_date":      self.match_date,
            "similarity":      round(self.similarity, 3),
            "indicators":      self.indicators,
            "forward_returns": self.forward_returns,
            "description":     self.description,
        }


class HistoricalPatternMatcher:
    """Find past situations with similar indicator signatures."""

    def __init__(self, lookback_windows: list[int] = None):
        self.windows = lookback_windows or FORWARD_WINDOWS

    def find_matches(
        self,
        signal: StockSignal,
        top_k: int = 5,
        min_similarity: float = 0.70,
    ) -> list[HistoricalMatch]:
        """
        Scan the stock's own history for similar indicator conditions.
        Returns up to `top_k` matches sorted by similarity (best first).
        """
        df = signal.price_history
        if df is None or len(df) < 60:
            return []

        close  = df["Close"]
        high   = df["High"]
        low    = df["Low"]
        volume = df["Volume"]

        # Pre-compute indicator series for the full history
        rsi_s          = _rsi(close)
        _, _, macd_h_s = _macd(close)
        _, _, _, pctb_s = _bollinger(close)
        stk_s, _       = _stochastic(high, low, close)
        ema20_s        = _ema(close, 20)
        ema50_s        = _ema(close, 50)
        ema200_s       = _ema(close, 200)
        vwap_s         = _vwap(df)
        vol_avg_s      = volume.rolling(20).mean()

        # Current feature vector (the "today" snapshot)
        current_vec = self._build_vector(
            rsi_val     = float(rsi_s.iloc[-1]),
            macd_h_val  = float(macd_h_s.iloc[-1]),
            pctb_val    = float(pctb_s.iloc[-1]),
            stk_val     = float(stk_s.iloc[-1]),
            ema20_val   = float(ema20_s.iloc[-1]),
            ema50_val   = float(ema50_s.iloc[-1]),
            ema200_val  = float(ema200_s.iloc[-1]),
            price_val   = float(close.iloc[-1]),
            vwap_val    = float(vwap_s.iloc[-1]),
            vol_ratio   = float(volume.iloc[-1]) / (float(vol_avg_s.iloc[-1]) + 1e-9),
        )

        max_forward = max(self.windows)
        # Scan history (skip first 200 rows for EMA200 warmup, skip last max_forward for forward returns)
        start_idx = min(200, len(df) - max_forward - 10)
        if start_idx < 30:
            start_idx = 30
        end_idx = len(df) - max_forward - 1

        if end_idx <= start_idx:
            return []

        candidates = []
        # Scan every 3rd row for speed
        for i in range(start_idx, end_idx, 3):
            try:
                vec = self._build_vector(
                    rsi_val     = float(rsi_s.iloc[i]),
                    macd_h_val  = float(macd_h_s.iloc[i]),
                    pctb_val    = float(pctb_s.iloc[i]),
                    stk_val     = float(stk_s.iloc[i]),
                    ema20_val   = float(ema20_s.iloc[i]),
                    ema50_val   = float(ema50_s.iloc[i]),
                    ema200_val  = float(ema200_s.iloc[i]),
                    price_val   = float(close.iloc[i]),
                    vwap_val    = float(vwap_s.iloc[i]),
                    vol_ratio   = float(volume.iloc[i]) / (float(vol_avg_s.iloc[i]) + 1e-9),
                )
            except (IndexError, ValueError):
                continue

            if np.any(np.isnan(vec)):
                continue

            sim = float(cosine_similarity(
                current_vec.reshape(1, -1), vec.reshape(1, -1)
            )[0, 0])

            if sim >= min_similarity:
                # Compute forward returns
                p_now = float(close.iloc[i])
                fwd = {}
                for w in self.windows:
                    if i + w < len(close):
                        p_future = float(close.iloc[i + w])
                        fwd[f"{w}d"] = round((p_future - p_now) / p_now * 100, 2)
                    else:
                        fwd[f"{w}d"] = None

                date_str = df.index[i].strftime("%Y-%m-%d")
                indicators = {
                    "rsi":    round(float(rsi_s.iloc[i]), 1),
                    "macd_h": round(float(macd_h_s.iloc[i]), 4),
                    "pct_b":  round(float(pctb_s.iloc[i]), 3),
                    "stoch_k": round(float(stk_s.iloc[i]), 1),
                }

                # Build description
                ret_parts = []
                for w in self.windows:
                    key = f"{w}d"
                    if fwd.get(key) is not None:
                        direction = "rose" if fwd[key] > 0 else "fell"
                        ret_parts.append(f"{direction} {abs(fwd[key]):.1f}% in {w} days")

                desc = (
                    f"On {date_str}, indicators were {sim:.0%} similar "
                    f"(RSI={indicators['rsi']}, MACD_h={indicators['macd_h']:+.4f}). "
                    f"After that, the stock {'; '.join(ret_parts)}."
                )

                candidates.append(HistoricalMatch(
                    match_date=date_str,
                    similarity=sim,
                    indicators=indicators,
                    forward_returns=fwd,
                    description=desc,
                ))

        # Sort by similarity, take top_k
        candidates.sort(key=lambda m: m.similarity, reverse=True)
        return candidates[:top_k]

    def _build_vector(self, rsi_val, macd_h_val, pctb_val, stk_val,
                      ema20_val, ema50_val, ema200_val, price_val,
                      vwap_val, vol_ratio) -> np.ndarray:
        """Normalised 8-feature vector for similarity comparison."""
        # EMA alignment: +1 if bullish, -1 if bearish, 0 if mixed
        ema_align = 0.0
        if ema20_val > ema50_val: ema_align += 0.5
        if ema50_val > ema200_val: ema_align += 0.5
        if ema20_val < ema50_val: ema_align -= 0.5
        if ema50_val < ema200_val: ema_align -= 0.5

        # VWAP position
        vwap_pos = (price_val - vwap_val) / (vwap_val + 1e-9)

        return np.array([
            rsi_val / 100.0,                         # 0-1
            np.sign(macd_h_val),                     # -1, 0, +1
            min(abs(macd_h_val) * 10, 1.0),          # magnitude 0-1
            np.clip(pctb_val, 0, 1),                 # 0-1
            stk_val / 100.0,                         # 0-1
            (ema_align + 1) / 2.0,                   # 0-1
            np.clip(vwap_pos * 10 + 0.5, 0, 1),     # 0-1
            min(vol_ratio / 3.0, 1.0),               # 0-1
        ], dtype=np.float64)


def summarize_matches(matches: list[HistoricalMatch]) -> str:
    """Consensus summary across all matches."""
    if not matches:
        return "No similar historical patterns found in the available data."

    lines = [f"Found {len(matches)} similar historical patterns:"]
    lines.append("")

    # Consensus: for each window, count positive vs negative
    for w in FORWARD_WINDOWS:
        key = f"{w}d"
        returns = [m.forward_returns.get(key) for m in matches
                   if m.forward_returns.get(key) is not None]
        if not returns:
            continue
        positive = sum(1 for r in returns if r > 0)
        avg_ret  = sum(returns) / len(returns)
        win_rate = positive / len(returns) * 100
        lines.append(
            f"  {w}-day outlook: {positive}/{len(returns)} times stock went UP "
            f"({win_rate:.0f}% win rate), avg return: {avg_ret:+.1f}%"
        )

    lines.append("")
    for i, m in enumerate(matches, 1):
        lines.append(f"  Match {i}: {m.description}")

    return "\n".join(lines)
