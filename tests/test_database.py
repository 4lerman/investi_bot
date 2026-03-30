import pytest
import os
import aiosqlite
from unittest.mock import patch
from db import queries
from db.database import init_db
import db.database


@pytest.fixture(autouse=True)
async def setup_test_db(tmp_path):
    # Override DATABASE_PATH to use a temp db for tests
    db_path = str(tmp_path / "test_investment_bot.db")
    
    # Store the original and patch
    orig_path = db.database.DATABASE_PATH
    db.database.DATABASE_PATH = db_path
    
    # Initialize the tables
    await init_db()
    
    yield  # Run tests
    
    # Cleanup (optional as tmp_path is cleaned up by pytest, but good practice)
    db.database.DATABASE_PATH = orig_path


@pytest.mark.asyncio
async def test_create_and_get_user():
    await queries.create_user(123, "testuser")
    user = await queries.get_user(123)
    
    assert user is not None
    assert user["user_id"] == 123
    assert user["username"] == "testuser"
    assert user["tier"] == "free"
    assert user["analyze_count"] == 0
    assert user["budget"] == 95.0


@pytest.mark.asyncio
async def test_update_user():
    await queries.create_user(456, "updateme")
    await queries.update_user(456, budget=200.0, risk="high", tier="premium")
    
    user = await queries.get_user(456)
    assert user["budget"] == 200.0
    assert user["risk"] == "high"
    assert user["tier"] == "premium"


@pytest.mark.asyncio
async def test_holdings_crud():
    await queries.create_user(111, "holder")
    
    # Add holdings
    await queries.add_holding(111, "AAPL", 10.5, 150.0)
    await queries.add_holding(111, "TSLA", 5.0, 200.0)
    
    holdings = await queries.get_holdings(111)
    assert len(holdings) == 2
    assert holdings[0]["ticker"] == "AAPL"
    assert holdings[1]["ticker"] == "TSLA"
    
    # Remove holding by ID
    aapl_id = holdings[0]["id"]
    removed = await queries.remove_holding(aapl_id, 111)
    assert removed is True
    
    holdings_after = await queries.get_holdings(111)
    assert len(holdings_after) == 1
    
    # Remove by ticker
    removed_ticker = await queries.remove_holding_by_ticker(111, "TSLA")
    assert removed_ticker is True
    
    final_holdings = await queries.get_holdings(111)
    assert len(final_holdings) == 0


@pytest.mark.asyncio
async def test_analyze_count_limits():
    await queries.create_user(999, "limituser")
    user = await queries.get_user(999)
    assert user["analyze_count"] == 0
    
    await queries.increment_analyze_count(999)
    await queries.increment_analyze_count(999)
    
    user_after = await queries.get_user(999)
    assert user_after["analyze_count"] == 2
    
    # Reset counts
    await queries.reset_analyze_counts()
    user_reset = await queries.get_user(999)
    assert user_reset["analyze_count"] == 0
