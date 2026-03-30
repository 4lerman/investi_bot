import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import requests
import yfinance as yf

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, datetime]] = {}
CACHE_TTL = timedelta(minutes=15)

_FINNHUB_KEY: str | None = os.getenv("FINNHUB_API_KEY") or None
_FINNHUB_URL = "https://api.finnhub.io/api/v1/quote"


def _is_cached(ticker: str) -> bool:
    if ticker not in _cache:
        return False
    _, ts = _cache[ticker]
    return datetime.now(timezone.utc) - ts < CACHE_TTL


async def get_price(ticker: str) -> float | None:
    ticker = ticker.upper()
    if _is_cached(ticker):
        return _cache[ticker][0]
    try:
        price = await asyncio.to_thread(_fetch_price, ticker)
        if price is not None:
            _cache[ticker] = (price, datetime.now(timezone.utc))
        return price
    except Exception as e:
        logger.error("get_price error for %s: %s", ticker, e)
        return None


def _fetch_price_yfinance(ticker: str) -> float | None:
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        return None
    except Exception as e:
        logger.warning("yfinance failed for %s: %s", ticker, e)
        return None


def _fetch_price_finnhub(ticker: str) -> float | None:
    try:
        resp = requests.get(
            _FINNHUB_URL,
            params={"symbol": ticker, "token": _FINNHUB_KEY},
            timeout=5,
        )
        resp.raise_for_status()
        price = resp.json().get("c", 0)
        return float(price) if price and price > 0 else None
    except Exception as e:
        logger.warning("Finnhub failed for %s: %s", ticker, e)
        return None


def _fetch_price_with_fallback(ticker: str) -> float | None:
    price = _fetch_price_yfinance(ticker)
    if price is not None:
        return price
    if not _FINNHUB_KEY:
        logger.warning("yfinance returned None for %s; no Finnhub key set", ticker)
        return None
    logger.info("yfinance returned None for %s; trying Finnhub", ticker)
    price = _fetch_price_finnhub(ticker)
    if price is not None:
        logger.info("Finnhub found price for %s: %.2f", ticker, price)
    else:
        logger.warning("Both providers returned no data for %s — ticker may not exist or is not listed on US exchanges", ticker)
    return price


def _fetch_price(ticker: str) -> float | None:
    return _fetch_price_with_fallback(ticker)


async def get_prices(tickers: list[str]) -> dict[str, float]:
    tickers = [t.upper() for t in tickers]
    results: dict[str, float] = {}

    need_fetch = [t for t in tickers if not _is_cached(t)]
    for t in tickers:
        if _is_cached(t):
            results[t] = _cache[t][0]

    if need_fetch:
        fetched = await asyncio.to_thread(_batch_fetch, need_fetch)
        for t, price in fetched.items():
            if price is not None:
                _cache[t] = (price, datetime.now(timezone.utc))
                results[t] = price

    return results


def _batch_fetch(tickers: list[str]) -> dict[str, float | None]:
    results: dict[str, float | None] = {}
    for t in tickers:
        results[t] = _fetch_price(t)
    return results
