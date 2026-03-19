"""
International Markets Definition
----------------------------------
Defines supported exchanges, ticker suffixes, currencies,
and popular stocks for each market.
"""

MARKETS = {
    "nse_india": {
        "name": "NSE India",
        "flag": "🇮🇳",
        "suffix": ".NS",
        "currency": "₹",
        "currency_code": "INR",
        "placeholder": "e.g. INFY or Infosys",
        "popular": [
            {"ticker": "RELIANCE.NS", "name": "Reliance Industries"},
            {"ticker": "TCS.NS",      "name": "Tata Consultancy Services"},
            {"ticker": "HDFCBANK.NS", "name": "HDFC Bank"},
            {"ticker": "INFY.NS",     "name": "Infosys"},
            {"ticker": "ICICIBANK.NS","name": "ICICI Bank"},
            {"ticker": "HINDUNILVR.NS","name": "Hindustan Unilever"},
            {"ticker": "ITC.NS",      "name": "ITC"},
            {"ticker": "SBIN.NS",     "name": "State Bank of India"},
            {"ticker": "BAJFINANCE.NS","name": "Bajaj Finance"},
            {"ticker": "WIPRO.NS",    "name": "Wipro"},
        ],
    },
    "us": {
        "name": "US Markets",
        "flag": "🇺🇸",
        "suffix": "",
        "currency": "$",
        "currency_code": "USD",
        "placeholder": "e.g. AAPL or Apple",
        "popular": [
            {"ticker": "AAPL",  "name": "Apple Inc."},
            {"ticker": "MSFT",  "name": "Microsoft"},
            {"ticker": "GOOGL", "name": "Alphabet (Google)"},
            {"ticker": "AMZN",  "name": "Amazon"},
            {"ticker": "NVDA",  "name": "NVIDIA"},
            {"ticker": "META",  "name": "Meta Platforms"},
            {"ticker": "TSLA",  "name": "Tesla"},
            {"ticker": "BRK-B", "name": "Berkshire Hathaway"},
            {"ticker": "JPM",   "name": "JPMorgan Chase"},
            {"ticker": "V",     "name": "Visa"},
            {"ticker": "JNJ",   "name": "Johnson & Johnson"},
            {"ticker": "WMT",   "name": "Walmart"},
        ],
    },
    "lse": {
        "name": "London Stock Exchange",
        "flag": "🇬🇧",
        "suffix": ".L",
        "currency": "£",
        "currency_code": "GBP",
        "placeholder": "e.g. HSBA or LLOY",
        "popular": [
            {"ticker": "HSBA.L",  "name": "HSBC Holdings"},
            {"ticker": "BP.L",    "name": "BP plc"},
            {"ticker": "SHEL.L",  "name": "Shell plc"},
            {"ticker": "AZN.L",   "name": "AstraZeneca"},
            {"ticker": "GSK.L",   "name": "GSK plc"},
            {"ticker": "LLOY.L",  "name": "Lloyds Banking Group"},
            {"ticker": "BARC.L",  "name": "Barclays"},
            {"ticker": "VOD.L",   "name": "Vodafone Group"},
            {"ticker": "RIO.L",   "name": "Rio Tinto"},
            {"ticker": "BA.L",    "name": "BAE Systems"},
        ],
    },
    "frankfurt": {
        "name": "Frankfurt (Germany)",
        "flag": "🇩🇪",
        "suffix": ".DE",
        "currency": "€",
        "currency_code": "EUR",
        "placeholder": "e.g. SAP or BMW",
        "popular": [
            {"ticker": "SAP.DE",  "name": "SAP SE"},
            {"ticker": "BMW.DE",  "name": "BMW AG"},
            {"ticker": "VOW3.DE", "name": "Volkswagen"},
            {"ticker": "BAYN.DE", "name": "Bayer AG"},
            {"ticker": "SIE.DE",  "name": "Siemens AG"},
            {"ticker": "ALV.DE",  "name": "Allianz SE"},
            {"ticker": "DBK.DE",  "name": "Deutsche Bank"},
            {"ticker": "ADS.DE",  "name": "Adidas"},
            {"ticker": "DTE.DE",  "name": "Deutsche Telekom"},
            {"ticker": "MBG.DE",  "name": "Mercedes-Benz"},
        ],
    },
    "tokyo": {
        "name": "Tokyo (Japan)",
        "flag": "🇯🇵",
        "suffix": ".T",
        "currency": "¥",
        "currency_code": "JPY",
        "placeholder": "e.g. 7203 (Toyota) or 6758 (Sony)",
        "popular": [
            {"ticker": "7203.T",  "name": "Toyota Motor"},
            {"ticker": "6758.T",  "name": "Sony Group"},
            {"ticker": "9984.T",  "name": "SoftBank Group"},
            {"ticker": "6861.T",  "name": "Keyence"},
            {"ticker": "8306.T",  "name": "Mitsubishi UFJ"},
            {"ticker": "9432.T",  "name": "NTT Corp"},
            {"ticker": "7974.T",  "name": "Nintendo"},
            {"ticker": "6501.T",  "name": "Hitachi"},
            {"ticker": "4063.T",  "name": "Shin-Etsu Chemical"},
            {"ticker": "8035.T",  "name": "Tokyo Electron"},
        ],
    },
    "hkex": {
        "name": "Hong Kong (HKEX)",
        "flag": "🇭🇰",
        "suffix": ".HK",
        "currency": "HK$",
        "currency_code": "HKD",
        "placeholder": "e.g. 0700 (Tencent) or 0005 (HSBC)",
        "popular": [
            {"ticker": "0700.HK", "name": "Tencent Holdings"},
            {"ticker": "9988.HK", "name": "Alibaba Group"},
            {"ticker": "0005.HK", "name": "HSBC Holdings"},
            {"ticker": "1299.HK", "name": "AIA Group"},
            {"ticker": "0941.HK", "name": "China Mobile"},
            {"ticker": "2318.HK", "name": "Ping An Insurance"},
            {"ticker": "3690.HK", "name": "Meituan"},
            {"ticker": "9618.HK", "name": "JD.com"},
            {"ticker": "0388.HK", "name": "HKEX"},
            {"ticker": "1177.HK", "name": "Sino Biopharmaceutical"},
        ],
    },
    "asx": {
        "name": "Australia (ASX)",
        "flag": "🇦🇺",
        "suffix": ".AX",
        "currency": "A$",
        "currency_code": "AUD",
        "placeholder": "e.g. CBA or BHP",
        "popular": [
            {"ticker": "CBA.AX",  "name": "Commonwealth Bank"},
            {"ticker": "BHP.AX",  "name": "BHP Group"},
            {"ticker": "CSL.AX",  "name": "CSL Limited"},
            {"ticker": "NAB.AX",  "name": "National Australia Bank"},
            {"ticker": "WBC.AX",  "name": "Westpac Banking"},
            {"ticker": "ANZ.AX",  "name": "ANZ Group"},
            {"ticker": "WES.AX",  "name": "Wesfarmers"},
            {"ticker": "MQG.AX",  "name": "Macquarie Group"},
            {"ticker": "RIO.AX",  "name": "Rio Tinto"},
            {"ticker": "TLS.AX",  "name": "Telstra"},
        ],
    },
    "sgx": {
        "name": "Singapore (SGX)",
        "flag": "🇸🇬",
        "suffix": ".SI",
        "currency": "S$",
        "currency_code": "SGD",
        "placeholder": "e.g. D05 (DBS) or Z74 (SingTel)",
        "popular": [
            {"ticker": "D05.SI",  "name": "DBS Group"},
            {"ticker": "O39.SI",  "name": "OCBC Bank"},
            {"ticker": "U11.SI",  "name": "United Overseas Bank"},
            {"ticker": "Z74.SI",  "name": "Singapore Telecom"},
            {"ticker": "C6L.SI",  "name": "Singapore Airlines"},
            {"ticker": "BN4.SI",  "name": "Keppel Corp"},
            {"ticker": "F34.SI",  "name": "Wilmar International"},
            {"ticker": "G13.SI",  "name": "Genting Singapore"},
            {"ticker": "S58.SI",  "name": "SATS"},
            {"ticker": "C38U.SI", "name": "CapitaLand Integrated"},
        ],
    },
}

MARKET_LIST = list(MARKETS.keys())


def get_market(market_id: str) -> dict:
    return MARKETS.get(market_id, MARKETS["nse_india"])


def get_currency_symbol(market_id: str) -> str:
    return MARKETS.get(market_id, {}).get("currency", "₹")


def add_suffix(symbol: str, market_id: str) -> str:
    """Add exchange suffix to a bare symbol if not already present."""
    suffix = MARKETS.get(market_id, {}).get("suffix", "")
    if suffix and not symbol.endswith(suffix):
        return symbol + suffix
    return symbol


def strip_suffix(ticker: str) -> str:
    """Remove exchange suffix for display."""
    for m in MARKETS.values():
        sfx = m.get("suffix", "")
        if sfx and ticker.endswith(sfx):
            return ticker[: -len(sfx)]
    return ticker
