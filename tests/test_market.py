import pytest
from unittest.mock import patch, MagicMock
from core import market
from datetime import datetime, timedelta

@pytest.fixture(autouse=True)
def clear_cache():
    market._cache.clear()
    yield
    market._cache.clear()

@pytest.mark.asyncio
@patch("core.market.yf.Ticker")
async def test_get_price_success(mock_ticker):
    # Setup mock
    mock_hist = MagicMock()
    mock_hist.empty = False
    mock_hist.__getitem__.return_value.iloc = [148.5, 150.25]  # Simulate returning closing prices, latest is 150.25
    mock_ticker.return_value.history.return_value = mock_hist
    
    price = await market.get_price("AAPL")
    
    assert price == 150.25
    mock_ticker.assert_called_once_with("AAPL")
    
    # Test caching: Second call should not hit yfinance
    mock_ticker.reset_mock()
    cached_price = await market.get_price("AAPL")
    
    assert cached_price == 150.25
    mock_ticker.assert_not_called()

@pytest.mark.asyncio
@patch("core.market.yf.Ticker")
async def test_get_price_invalid_ticker(mock_ticker):
    mock_hist = MagicMock()
    mock_hist.empty = True
    mock_ticker.return_value.history.return_value = mock_hist
    
    price = await market.get_price("INVALIDXYZ")
    
    assert price is None
    
    # Should not be cached if none returned
    assert "INVALIDXYZ" not in market._cache

@pytest.mark.asyncio
@patch("core.market.yf.Ticker")
async def test_get_price_exception(mock_ticker):
    mock_ticker.return_value.history.side_effect = Exception("Network Error")
    
    price = await market.get_price("AAPL")
    
    assert price is None
