"""
Indian Mutual Funds via MFAPI.in
----------------------------------
Free, no API key required.
API docs: https://www.mfapi.in/

Endpoints used:
  Search:   GET https://api.mfapi.in/mf/search?q=<query>
  NAV data: GET https://api.mfapi.in/mf/<scheme_code>
"""

import requests
from typing import Optional

MFAPI_BASE = "https://api.mfapi.in/mf"
HEADERS = {"User-Agent": "Mozilla/5.0 StockAnalysisApp/1.0"}

# Prefix used in paper broker to identify MF positions
MF_TICKER_PREFIX = "MF:"


def search_funds(query: str) -> list[dict]:
    """Search for mutual funds by name or fund house.

    Returns list of dicts with:
      scheme_code, scheme_name, fund_house, scheme_type, scheme_category
    """
    if not query or len(query) < 2:
        return []
    try:
        resp = requests.get(
            f"{MFAPI_BASE}/search",
            params={"q": query},
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        results = resp.json()
        # Normalise keys
        return [
            {
                "scheme_code":     r.get("schemeCode", ""),
                "scheme_name":     r.get("schemeName", ""),
                "fund_house":      r.get("fundHouse", ""),
                "scheme_type":     r.get("schemeType", ""),
                "scheme_category": r.get("schemeCategory", ""),
                "ticker":          f"{MF_TICKER_PREFIX}{r.get('schemeCode', '')}",
            }
            for r in results[:20]
        ]
    except Exception:
        return []


def get_fund_nav(scheme_code: str) -> Optional[dict]:
    """Get latest NAV and historical data for a scheme.

    Returns dict with:
      scheme_code, scheme_name, fund_house, scheme_type, scheme_category,
      nav (float), nav_date (str), nav_history (list of {date, nav})
    """
    try:
        resp = requests.get(
            f"{MFAPI_BASE}/{scheme_code}",
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()

        meta = data.get("meta", {})
        nav_data = data.get("data", [])

        # Latest NAV is first in the list
        latest = nav_data[0] if nav_data else {}
        nav_val = float(latest.get("nav", 0)) if latest else 0
        nav_date = latest.get("date", "")

        # Build 1-year history for chart (data is newest-first, reverse for chart)
        history = [
            {"date": d["date"], "nav": float(d["nav"])}
            for d in nav_data[:365]
            if d.get("nav") and d["nav"] != "N.A."
        ]
        history.reverse()  # oldest first for chart

        return {
            "scheme_code":     scheme_code,
            "scheme_name":     meta.get("scheme_name", ""),
            "fund_house":      meta.get("fund_house", ""),
            "scheme_type":     meta.get("scheme_type", ""),
            "scheme_category": meta.get("scheme_category", ""),
            "nav":             round(nav_val, 4),
            "nav_date":        nav_date,
            "nav_history":     history,
            "ticker":          f"{MF_TICKER_PREFIX}{scheme_code}",
            # 1-year return
            "return_1y":       _calc_return(history, 365),
            "return_6m":       _calc_return(history, 182),
            "return_1m":       _calc_return(history, 30),
        }
    except Exception:
        return None


def _calc_return(history: list, days: int) -> Optional[float]:
    """Calculate % return over `days` trading days from history list."""
    if len(history) < 2:
        return None
    current_nav = history[-1]["nav"]
    # Find NAV approximately `days` ago
    idx = max(0, len(history) - days)
    past_nav = history[idx]["nav"]
    if past_nav == 0:
        return None
    return round((current_nav - past_nav) / past_nav * 100, 2)


def make_mf_ticker(scheme_code: str) -> str:
    return f"{MF_TICKER_PREFIX}{scheme_code}"


def parse_mf_ticker(ticker: str) -> Optional[str]:
    """Extract scheme code from MF ticker like 'MF:119551'. Returns None if not an MF ticker."""
    if ticker.startswith(MF_TICKER_PREFIX):
        return ticker[len(MF_TICKER_PREFIX):]
    return None


def is_mf_ticker(ticker: str) -> bool:
    return ticker.startswith(MF_TICKER_PREFIX)


# Popular fund categories for quick navigation
POPULAR_CATEGORIES = [
    "Large Cap Fund",
    "Mid Cap Fund",
    "Small Cap Fund",
    "Flexi Cap Fund",
    "ELSS",
    "Index Fund",
    "Liquid Fund",
    "Hybrid Aggressive",
]

# Some well-known funds (scheme codes from AMFI)
POPULAR_FUNDS = [
    {"scheme_code": "120503", "scheme_name": "Mirae Asset Large Cap Fund - Direct Growth",     "fund_house": "Mirae Asset"},
    {"scheme_code": "119598", "scheme_name": "Axis Bluechip Fund - Direct Plan - Growth",      "fund_house": "Axis MF"},
    {"scheme_code": "100356", "scheme_name": "SBI Small Cap Fund - Direct Plan - Growth",     "fund_house": "SBI MF"},
    {"scheme_code": "119551", "scheme_name": "Parag Parikh Flexi Cap Fund - Direct Growth",   "fund_house": "PPFAS"},
    {"scheme_code": "118989", "scheme_name": "Quant Small Cap Fund - Direct Plan - Growth",   "fund_house": "Quant MF"},
    {"scheme_code": "120594", "scheme_name": "HDFC Flexi Cap Fund - Direct Plan - Growth",    "fund_house": "HDFC MF"},
    {"scheme_code": "101206", "scheme_name": "Nippon India Small Cap Fund - Direct Growth",   "fund_house": "Nippon MF"},
    {"scheme_code": "120716", "scheme_name": "Kotak Emerging Equity Fund - Direct Growth",    "fund_house": "Kotak MF"},
    {"scheme_code": "148620", "scheme_name": "Navi Nifty 50 Index Fund - Direct Growth",      "fund_house": "Navi MF"},
    {"scheme_code": "120684", "scheme_name": "UTI Nifty 50 Index Fund - Direct Growth",       "fund_house": "UTI MF"},
]
