"""Curated ETF watchlists and market-data fetch utilities."""

import asyncio
import logging
from datetime import datetime, timedelta

import yfinance as yf

logger = logging.getLogger(__name__)

# ── Curated watchlists ────────────────────────────────────────────────────

GENERAL_ETFS: dict[str, str] = {
    # Broad market
    "VOO": "Vanguard S&P 500 ETF",
    "VTI": "Vanguard Total Stock Market ETF",
    "QQQ": "Invesco Nasdaq-100 ETF",
    "IWM": "iShares Russell 2000 ETF",
    "VEA": "Vanguard FTSE Developed Markets ETF",
    "VWO": "Vanguard FTSE Emerging Markets ETF",
    # Bonds / income
    "BND": "Vanguard Total Bond Market ETF",
    "SCHD": "Schwab U.S. Dividend Equity ETF",
    "VYM": "Vanguard High Dividend Yield ETF",
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    # Sector
    "XLK": "Technology Select Sector SPDR",
    "XLV": "Health Care Select Sector SPDR",
    "XLE": "Energy Select Sector SPDR",
    "XLF": "Financial Select Sector SPDR",
    "XLRE": "Real Estate Select Sector SPDR",
    # Thematic / growth
    "ARKK": "ARK Innovation ETF",
    "SOXX": "iShares Semiconductor ETF",
    "ICLN": "iShares Global Clean Energy ETF",
    # Defensive / low-vol
    "GLD": "SPDR Gold Shares",
    "SHY": "iShares 1-3 Year Treasury Bond ETF",
    "USMV": "iShares MSCI USA Min Vol Factor ETF",
    # International
    "EFA": "iShares MSCI EAFE ETF",
    "IEMG": "iShares Core MSCI Emerging Markets ETF",
    # Balanced
    "AOR": "iShares Core Growth Allocation ETF",
    "VT": "Vanguard Total World Stock ETF",
}

HALAL_ETFS: dict[str, str] = {
    "SPUS": "SP Funds S&P 500 Sharia Industry Exclusions ETF",
    "HLAL": "Wahed FTSE USA Shariah ETF",
    "UMMA": "Wahed Dow Jones Islamic World ETF",
    "SPRE": "SP Funds S&P Global REIT Sharia ETF",
    "SPSK": "SP Funds Dow Jones Global Sukuk ETF",
    "SPTE": "SP Funds S&P 500 Sharia Technology ETF",
    "SPWO": "SP Funds S&P World (ex-US) ETF",
    "APTS": "Apartment Investment and Management Co",
}

# ── Watchlist cache (30-min TTL) ──────────────────────────────────────────

_watchlist_cache: dict[str, tuple[dict[str, dict], datetime]] = {}
_WATCHLIST_CACHE_TTL = timedelta(minutes=30)


def get_watchlist(shariah: bool = False) -> dict[str, str]:
    """Return the appropriate watchlist based on user preference."""
    return HALAL_ETFS if shariah else GENERAL_ETFS


# ── yfinance helpers ──────────────────────────────────────────────────────

def _fetch_ticker_data(ticker: str) -> dict | None:
    """Fetch current price and 1-month performance for a single ticker."""
    try:
        hist = yf.Ticker(ticker).history(period="1mo")
        if hist.empty or len(hist) < 2:
            return None
        current = float(hist["Close"].iloc[-1])
        month_ago = float(hist["Close"].iloc[0])
        change_pct = ((current - month_ago) / month_ago) * 100
        return {"price": current, "change_1m_pct": change_pct}
    except Exception as e:
        logger.error("_fetch_ticker_data error for %s: %s", ticker, e)
        return None


def _batch_fetch(tickers: list[str]) -> dict[str, dict]:
    """Fetch data for a list of tickers sequentially (runs in a thread)."""
    results = {}
    for t in tickers:
        data = _fetch_ticker_data(t)
        if data is not None:
            results[t] = data
    return results


async def fetch_watchlist_data(
    watchlist: dict[str, str],
    exclude_tickers: list[str] | None = None,
) -> dict[str, dict]:
    """Fetch price + 1-month performance for watchlist tickers.

    Returns: {ticker: {"name": str, "price": float, "change_1m_pct": float}}
    Uses a 30-min cache keyed by the watchlist identity.
    """
    exclude = {t.upper() for t in (exclude_tickers or [])}
    candidates = {t: name for t, name in watchlist.items() if t not in exclude}

    # Check cache (keyed on frozenset of full watchlist, not filtered)
    cache_key = ",".join(sorted(watchlist.keys()))
    now = datetime.utcnow()
    if cache_key in _watchlist_cache:
        cached_data, cached_at = _watchlist_cache[cache_key]
        if now - cached_at < _WATCHLIST_CACHE_TTL:
            return {
                t: cached_data[t]
                for t in candidates
                if t in cached_data
            }

    # Fetch all watchlist tickers (not just filtered ones) so the cache is complete
    raw = await asyncio.to_thread(_batch_fetch, list(watchlist.keys()))

    # Build full cache entry
    full_data: dict[str, dict] = {}
    for ticker, data in raw.items():
        full_data[ticker] = {
            "name": watchlist[ticker],
            "price": data["price"],
            "change_1m_pct": data["change_1m_pct"],
        }
    _watchlist_cache[cache_key] = (full_data, now)

    # Return only the candidates (excluding user's holdings)
    return {t: full_data[t] for t in candidates if t in full_data}


def format_watchlist_for_prompt(watchlist_data: dict[str, dict]) -> str:
    """Format watchlist data as text for the LLM prompt."""
    lines = []
    for ticker, info in sorted(watchlist_data.items()):
        lines.append(
            f"  {ticker} ({info['name']}) — "
            f"${info['price']:.2f}, 1-month change: {info['change_1m_pct']:+.1f}%"
        )
    return "\n".join(lines) if lines else "  (no candidate data available)"
