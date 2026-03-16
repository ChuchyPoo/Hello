"""
Google Finance Data Fetcher
----------------------------
Scrapes stock data from Google Finance as primary source.
Falls back to Yahoo Finance (yfinance) if Google fails.
"""

import re
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import warnings
warnings.filterwarnings("ignore")

# Google Finance base URL
GOOGLE_FINANCE_URL = "https://www.google.com/finance/quote/{symbol}:{exchange}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _parse_google_number(text: str) -> Optional[float]:
    """Parse a number from Google Finance text (handles commas, currency symbols)."""
    if not text:
        return None
    cleaned = re.sub(r'[^\d.\-]', '', text.replace(',', ''))
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _ticker_to_google(ticker: str) -> tuple[str, str]:
    """Convert yfinance-style ticker to Google Finance symbol:exchange format.

    Examples:
        INFY.NS -> INFY:NSE
        RELIANCE.NS -> RELIANCE:NSE
        AAPL -> AAPL:NASDAQ
        MSFT -> MSFT:NASDAQ
    """
    if ticker.endswith('.NS'):
        symbol = ticker.replace('.NS', '')
        return symbol, 'NSE'
    elif ticker.endswith('.BO'):
        symbol = ticker.replace('.BO', '')
        return symbol, 'BOM'
    else:
        # US stocks - try NASDAQ first, then NYSE
        return ticker, 'NASDAQ'


def fetch_google_finance_quote(ticker: str) -> Optional[dict]:
    """Fetch current stock data from Google Finance.

    Returns dict with keys: price, change, change_pct, prev_close,
    open, high, low, volume, market_cap, pe_ratio, dividend_yield,
    year_high, year_low, name, exchange, currency
    """
    symbol, exchange = _ticker_to_google(ticker)
    url = GOOGLE_FINANCE_URL.format(symbol=symbol, exchange=exchange)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            # Try alternate exchange for US stocks
            if exchange == 'NASDAQ':
                url = GOOGLE_FINANCE_URL.format(symbol=symbol, exchange='NYSE')
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code != 200:
                    return None
            else:
                return None

        html = resp.text
        data = {}

        # Extract current price - look for the main price element
        # Google Finance uses specific data attributes
        price_patterns = [
            r'data-last-price="([^"]+)"',
            r'class="YMlKec fxKbKc"[^>]*>([^<]+)',
            r'class="YMlKec fxKbKc">.*?([0-9,]+\.\d+)',
        ]
        for pattern in price_patterns:
            match = re.search(pattern, html)
            if match:
                price = _parse_google_number(match.group(1))
                if price and price > 0:
                    data['price'] = price
                    break

        # Extract change and change percent
        change_match = re.search(r'data-currency-code="([^"]+)"', html)
        if change_match:
            data['currency'] = change_match.group(1)

        # Previous close
        prev_match = re.search(r'Previous close.*?([0-9,]+\.\d+)', html, re.DOTALL)
        if prev_match:
            data['prev_close'] = _parse_google_number(prev_match.group(1))

        # Day range (high/low)
        range_match = re.search(r'Day range.*?([0-9,]+\.\d+)\s*[-\u2013]\s*([0-9,]+\.\d+)', html, re.DOTALL)
        if range_match:
            data['low'] = _parse_google_number(range_match.group(1))
            data['high'] = _parse_google_number(range_match.group(2))

        # Year range
        year_match = re.search(r'Year range.*?([0-9,]+\.\d+)\s*[-\u2013]\s*([0-9,]+\.\d+)', html, re.DOTALL)
        if year_match:
            data['year_low'] = _parse_google_number(year_match.group(1))
            data['year_high'] = _parse_google_number(year_match.group(2))

        # Market cap
        mcap_match = re.search(r'Market cap.*?([0-9,.]+[TBMK]?)\s*(USD|INR)?', html, re.DOTALL)
        if mcap_match:
            data['market_cap_str'] = mcap_match.group(1)

        # P/E ratio
        pe_match = re.search(r'P/E ratio.*?([0-9,.]+)', html, re.DOTALL)
        if pe_match:
            data['pe_ratio'] = _parse_google_number(pe_match.group(1))

        # Dividend yield
        div_match = re.search(r'Dividend yield.*?([0-9,.]+)%', html, re.DOTALL)
        if div_match:
            data['dividend_yield'] = _parse_google_number(div_match.group(1))

        # Volume
        vol_match = re.search(r'(?:Avg )?[Vv]olume.*?([0-9,.]+[TBMK]?)', html, re.DOTALL)
        if vol_match:
            data['volume_str'] = vol_match.group(1)

        # Company name
        name_match = re.search(r'<div class="zzDege"[^>]*>([^<]+)', html)
        if name_match:
            data['name'] = name_match.group(1).strip()

        # About / description
        about_match = re.search(r'<div class="bLLb2d"[^>]*>(.*?)</div>', html, re.DOTALL)
        if about_match:
            desc = re.sub(r'<[^>]+>', '', about_match.group(1)).strip()
            if len(desc) > 20:
                data['description'] = desc[:500]

        data['source'] = 'google_finance'
        data['exchange'] = exchange
        data['symbol'] = symbol
        data['ticker'] = ticker

        if 'price' in data:
            return data
        return None

    except Exception as e:
        return None


def fetch_google_finance_details(ticker: str) -> Optional[dict]:
    """Fetch comprehensive data from Google Finance including financials, news, etc.

    Returns enriched data dict with additional fields beyond just price.
    """
    quote = fetch_google_finance_quote(ticker)
    if not quote:
        return None

    # Add computed fields
    if quote.get('price') and quote.get('prev_close'):
        quote['change'] = round(quote['price'] - quote['prev_close'], 2)
        quote['change_pct'] = round(
            (quote['price'] - quote['prev_close']) / quote['prev_close'] * 100, 2
        )

    return quote


def fetch_with_fallback(ticker: str, period: str = "1y", interval: str = "1d") -> tuple[Optional[pd.DataFrame], Optional[dict]]:
    """Fetch OHLCV data: try Google Finance for quote data,
    always use yfinance for historical OHLCV (Google doesn't provide downloadable history).
    Returns (dataframe, google_extra_data).

    Google Finance is used for:
    - Verifying the stock exists (better search/matching)
    - Extra fundamental data (P/E, market cap, dividend yield, etc.)
    - Current real-time price

    Yahoo Finance is used for:
    - Historical OHLCV data (charts, technical analysis)
    """
    import yfinance as yf

    google_data = fetch_google_finance_details(ticker)

    # Try Yahoo Finance for historical data
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # If Google gave us a more recent price, update the last row
            if google_data and google_data.get('price'):
                gp = google_data['price']
                last_close = float(df['Close'].iloc[-1])
                # Only update if significantly different (market might still be open)
                if abs(gp - last_close) / (last_close + 1e-9) > 0.001:
                    pass  # Don't modify historical data, just note it

            return df, google_data
    except Exception:
        pass

    # If Yahoo fails entirely but Google has a price, we can't do technical analysis
    # but we can at least return something
    if google_data and google_data.get('price'):
        return None, google_data

    return None, None


def search_google_finance(query: str) -> list[dict]:
    """Search for stocks on Google Finance.

    Returns list of matching stocks with basic info.
    """
    search_url = f"https://www.google.com/finance/search?q={requests.utils.quote(query)}"
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return []

        html = resp.text
        results = []

        # Extract search results
        # Pattern: ticker symbols and names from search results
        items = re.findall(
            r'/finance/quote/([^"?]+)"[^>]*>.*?<div class="[^"]*">([^<]+)',
            html, re.DOTALL
        )

        for raw_symbol, name in items[:10]:
            parts = raw_symbol.split(':')
            if len(parts) == 2:
                symbol, exchange = parts
                # Convert back to yfinance format
                if exchange == 'NSE':
                    ticker = f"{symbol}.NS"
                elif exchange == 'BOM':
                    ticker = f"{symbol}.BO"
                else:
                    ticker = symbol
                results.append({
                    'ticker': ticker,
                    'name': name.strip(),
                    'exchange': exchange,
                })

        return results
    except Exception:
        return []
