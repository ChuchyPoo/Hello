"""
NSE Stock Universe
------------------
Comprehensive list of NSE-listed stocks organised by sector.
Use get_all_tickers() for the full list, or filter by sector/price.
"""


# ── stock database ────────────────────────────────────────────────────────────

NSE_STOCKS = {
    "priority": [
        {"ticker": "TITAGARH.NS",   "name": "Titagarh Rail Systems"},
        {"ticker": "APOLLOTYRE.NS", "name": "Apollo Tyres"},
        {"ticker": "ETERNAL.NS",    "name": "Eternal (Zomato)"},
        {"ticker": "HINDCOPPER.NS", "name": "Hindustan Copper"},
    ],
    "banks": [
        {"ticker": "SBIN.NS",       "name": "State Bank of India"},
        {"ticker": "PNB.NS",        "name": "Punjab National Bank"},
        {"ticker": "BANKBARODA.NS", "name": "Bank of Baroda"},
        {"ticker": "CANBK.NS",      "name": "Canara Bank"},
        {"ticker": "UNIONBANK.NS",  "name": "Union Bank of India"},
        {"ticker": "IOB.NS",        "name": "Indian Overseas Bank"},
        {"ticker": "CENTRALBK.NS",  "name": "Central Bank of India"},
        {"ticker": "BANKINDIA.NS",  "name": "Bank of India"},
        {"ticker": "INDIANB.NS",    "name": "Indian Bank"},
        {"ticker": "YESBANK.NS",    "name": "Yes Bank"},
        {"ticker": "IDBI.NS",       "name": "IDBI Bank"},
        {"ticker": "FEDERALBNK.NS", "name": "Federal Bank"},
        {"ticker": "IDFCFIRSTB.NS", "name": "IDFC First Bank"},
        {"ticker": "RBLBANK.NS",    "name": "RBL Bank"},
        {"ticker": "MAHABANK.NS",   "name": "Bank of Maharashtra"},
        {"ticker": "UCOBANK.NS",    "name": "UCO Bank"},
    ],
    "it": [
        {"ticker": "TCS.NS",        "name": "Tata Consultancy Services"},
        {"ticker": "INFY.NS",       "name": "Infosys"},
        {"ticker": "WIPRO.NS",      "name": "Wipro"},
        {"ticker": "HCLTECH.NS",    "name": "HCL Technologies"},
        {"ticker": "TECHM.NS",      "name": "Tech Mahindra"},
        {"ticker": "LTIM.NS",       "name": "LTIMindtree"},
        {"ticker": "MPHASIS.NS",    "name": "Mphasis"},
        {"ticker": "COFORGE.NS",    "name": "Coforge"},
        {"ticker": "PERSISTENT.NS", "name": "Persistent Systems"},
        {"ticker": "TATAELXSI.NS",  "name": "Tata Elxsi"},
    ],
    "pharma": [
        {"ticker": "SUNPHARMA.NS",  "name": "Sun Pharma"},
        {"ticker": "DRREDDY.NS",    "name": "Dr Reddy's"},
        {"ticker": "CIPLA.NS",      "name": "Cipla"},
        {"ticker": "AUROPHARMA.NS", "name": "Aurobindo Pharma"},
        {"ticker": "LUPIN.NS",      "name": "Lupin"},
        {"ticker": "BIOCON.NS",     "name": "Biocon"},
        {"ticker": "GRANULES.NS",   "name": "Granules India"},
        {"ticker": "LAURUSLABS.NS", "name": "Laurus Labs"},
        {"ticker": "NATCOPHARM.NS", "name": "Natco Pharma"},
        {"ticker": "IPCALAB.NS",    "name": "IPCA Labs"},
    ],
    "auto": [
        {"ticker": "TATAMOTORS.NS", "name": "Tata Motors"},
        {"ticker": "M&M.NS",        "name": "Mahindra & Mahindra"},
        {"ticker": "MARUTI.NS",     "name": "Maruti Suzuki"},
        {"ticker": "BAJAJ-AUTO.NS", "name": "Bajaj Auto"},
        {"ticker": "HEROMOTOCO.NS", "name": "Hero MotoCorp"},
        {"ticker": "EICHERMOT.NS",  "name": "Eicher Motors"},
        {"ticker": "ASHOKLEY.NS",   "name": "Ashok Leyland"},
        {"ticker": "TVSMOTOR.NS",   "name": "TVS Motor"},
        {"ticker": "MRF.NS",        "name": "MRF"},
        {"ticker": "APOLLOTYRE.NS", "name": "Apollo Tyres"},
        {"ticker": "BALKRISIND.NS", "name": "Balkrishna Industries"},
        {"ticker": "MOTHERSON.NS",  "name": "Motherson Sumi"},
    ],
    "energy": [
        {"ticker": "RELIANCE.NS",   "name": "Reliance Industries"},
        {"ticker": "ONGC.NS",       "name": "ONGC"},
        {"ticker": "NTPC.NS",       "name": "NTPC"},
        {"ticker": "POWERGRID.NS",  "name": "Power Grid Corp"},
        {"ticker": "TATAPOWER.NS",  "name": "Tata Power"},
        {"ticker": "ADANIGREEN.NS", "name": "Adani Green Energy"},
        {"ticker": "ADANIPOWER.NS", "name": "Adani Power"},
        {"ticker": "NHPC.NS",       "name": "NHPC"},
        {"ticker": "SJVN.NS",       "name": "SJVN"},
        {"ticker": "TORNTPOWER.NS", "name": "Torrent Power"},
        {"ticker": "CESC.NS",       "name": "CESC"},
        {"ticker": "GAIL.NS",       "name": "GAIL India"},
        {"ticker": "IOC.NS",        "name": "Indian Oil Corp"},
        {"ticker": "BPCL.NS",       "name": "BPCL"},
        {"ticker": "HINDPETRO.NS",  "name": "Hindustan Petroleum"},
        {"ticker": "MRPL.NS",       "name": "Mangalore Refinery"},
    ],
    "metals": [
        {"ticker": "TATASTEEL.NS",  "name": "Tata Steel"},
        {"ticker": "JSWSTEEL.NS",   "name": "JSW Steel"},
        {"ticker": "HINDALCO.NS",   "name": "Hindalco"},
        {"ticker": "VEDL.NS",       "name": "Vedanta"},
        {"ticker": "SAIL.NS",       "name": "SAIL"},
        {"ticker": "NATIONALUM.NS", "name": "National Aluminium"},
        {"ticker": "HINDCOPPER.NS", "name": "Hindustan Copper"},
        {"ticker": "NMDC.NS",       "name": "NMDC"},
        {"ticker": "COALINDIA.NS",  "name": "Coal India"},
        {"ticker": "MOIL.NS",       "name": "MOIL"},
    ],
    "infra": [
        {"ticker": "IRFC.NS",       "name": "Indian Railway Finance"},
        {"ticker": "RVNL.NS",       "name": "Rail Vikas Nigam"},
        {"ticker": "IRCON.NS",      "name": "IRCON International"},
        {"ticker": "NBCC.NS",       "name": "NBCC India"},
        {"ticker": "HUDCO.NS",      "name": "HUDCO"},
        {"ticker": "RECLTD.NS",     "name": "REC Ltd"},
        {"ticker": "PFC.NS",        "name": "Power Finance Corp"},
        {"ticker": "LT.NS",         "name": "Larsen & Toubro"},
        {"ticker": "GMRINFRA.NS",   "name": "GMR Airports Infra"},
        {"ticker": "IRB.NS",        "name": "IRB Infra"},
        {"ticker": "NCC.NS",        "name": "NCC Ltd"},
        {"ticker": "TITAGARH.NS",   "name": "Titagarh Rail Systems"},
        {"ticker": "RITES.NS",      "name": "RITES"},
        {"ticker": "RAILTEL.NS",    "name": "RailTel Corp"},
        {"ticker": "COCHINSHIP.NS", "name": "Cochin Shipyard"},
    ],
    "defence": [
        {"ticker": "HAL.NS",        "name": "Hindustan Aeronautics"},
        {"ticker": "BEL.NS",        "name": "Bharat Electronics"},
        {"ticker": "BHEL.NS",       "name": "Bharat Heavy Electricals"},
        {"ticker": "BDL.NS",        "name": "Bharat Dynamics"},
        {"ticker": "MAZAGON.NS",    "name": "Mazagon Dock Shipbuilders"},
        {"ticker": "GRSE.NS",       "name": "Garden Reach Shipbuilders"},
        {"ticker": "DATAPATTNS.NS", "name": "Data Patterns"},
    ],
    "fmcg": [
        {"ticker": "HINDUNILVR.NS", "name": "Hindustan Unilever"},
        {"ticker": "ITC.NS",        "name": "ITC"},
        {"ticker": "NESTLEIND.NS",  "name": "Nestle India"},
        {"ticker": "BRITANNIA.NS",  "name": "Britannia"},
        {"ticker": "DABUR.NS",      "name": "Dabur India"},
        {"ticker": "MARICO.NS",     "name": "Marico"},
        {"ticker": "GODREJCP.NS",   "name": "Godrej Consumer"},
        {"ticker": "COLPAL.NS",     "name": "Colgate Palmolive"},
        {"ticker": "TATACONSUM.NS", "name": "Tata Consumer Products"},
        {"ticker": "VBL.NS",        "name": "Varun Beverages"},
    ],
    "realty": [
        {"ticker": "DLF.NS",        "name": "DLF"},
        {"ticker": "GODREJPROP.NS", "name": "Godrej Properties"},
        {"ticker": "OBEROIRLTY.NS", "name": "Oberoi Realty"},
        {"ticker": "PRESTIGE.NS",   "name": "Prestige Estates"},
        {"ticker": "LODHA.NS",      "name": "Macrotech (Lodha)"},
        {"ticker": "SOBHA.NS",      "name": "Sobha Ltd"},
        {"ticker": "BRIGADE.NS",    "name": "Brigade Enterprises"},
    ],
    "psu": [
        {"ticker": "IREDA.NS",      "name": "IREDA"},
        {"ticker": "SUZLON.NS",     "name": "Suzlon Energy"},
        {"ticker": "IDEA.NS",       "name": "Vodafone Idea"},
        {"ticker": "HFCL.NS",       "name": "HFCL"},
        {"ticker": "CDSL.NS",       "name": "CDSL"},
        {"ticker": "CAMS.NS",       "name": "CAMS"},
        {"ticker": "IEX.NS",        "name": "Indian Energy Exchange"},
        {"ticker": "IRCTC.NS",      "name": "IRCTC"},
        {"ticker": "CONCOR.NS",     "name": "Container Corp"},
    ],
    "chemicals": [
        {"ticker": "PIDILITIND.NS", "name": "Pidilite Industries"},
        {"ticker": "SRF.NS",        "name": "SRF Ltd"},
        {"ticker": "DEEPAKFERT.NS", "name": "Deepak Fertilisers"},
        {"ticker": "ATUL.NS",       "name": "Atul Ltd"},
        {"ticker": "CLEAN.NS",      "name": "Clean Science"},
        {"ticker": "GNFC.NS",       "name": "GNFC"},
        {"ticker": "CHAMBLFERT.NS", "name": "Chambal Fertilisers"},
    ],
    "media_tech": [
        {"ticker": "ZEEL.NS",       "name": "Zee Entertainment"},
        {"ticker": "NAUKRI.NS",     "name": "Info Edge (Naukri)"},
        {"ticker": "DELHIVERY.NS",  "name": "Delhivery"},
        {"ticker": "PAYTM.NS",      "name": "Paytm (One97)"},
        {"ticker": "POLICYBZR.NS",  "name": "PB Fintech"},
        {"ticker": "ETERNAL.NS",    "name": "Eternal (Zomato)"},
    ],
}

SECTOR_LIST = list(NSE_STOCKS.keys())


def get_all_tickers() -> list[str]:
    """Return flat list of all unique ticker strings."""
    seen = set()
    tickers = []
    for stocks in NSE_STOCKS.values():
        for s in stocks:
            if s["ticker"] not in seen:
                seen.add(s["ticker"])
                tickers.append(s["ticker"])
    return tickers


def get_by_sector(sector: str) -> list[str]:
    """Return tickers for a given sector key."""
    return [s["ticker"] for s in NSE_STOCKS.get(sector, [])]


def get_by_sectors(sectors: list[str]) -> list[str]:
    """Return tickers for multiple sectors."""
    seen = set()
    result = []
    for sec in sectors:
        for t in get_by_sector(sec):
            if t not in seen:
                seen.add(t)
                result.append(t)
    return result


def search_tickers(query: str) -> list[dict]:
    """Search by name or ticker substring (case-insensitive)."""
    q = query.upper()
    results = []
    for sector, stocks in NSE_STOCKS.items():
        for s in stocks:
            if q in s["ticker"].upper() or q in s["name"].upper():
                results.append({**s, "sector": sector})
    return results


def get_stock_info(ticker: str) -> dict | None:
    """Get name and sector for a ticker."""
    for sector, stocks in NSE_STOCKS.items():
        for s in stocks:
            if s["ticker"] == ticker:
                return {**s, "sector": sector}
    return None


# total count
TOTAL_STOCKS = len(get_all_tickers())
