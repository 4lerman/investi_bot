import sqlite3
from typing import Optional
from db.database import get_db


def _dict_factory(cursor, row) -> dict:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


# ── Users ──────────────────────────────────────────────────────────────────

async def get_user(user_id: int) -> Optional[dict]:
    async with get_db() as db:
        db.row_factory = _dict_factory
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            return await cursor.fetchone()


async def create_user(user_id: int, username: str) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username),
        )
        await db.commit()


async def update_user(user_id: int, **kwargs) -> None:
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [user_id]
    async with get_db() as db:
        await db.execute(f"UPDATE users SET {fields} WHERE user_id = ?", values)
        await db.commit()


async def get_all_users() -> list[dict]:
    async with get_db() as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM users") as cursor:
            return await cursor.fetchall()


async def increment_analyze_count(user_id: int) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET analyze_count = analyze_count + 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def reset_analyze_counts() -> None:
    async with get_db() as db:
        await db.execute("UPDATE users SET analyze_count = 0")
        await db.commit()


# ── Holdings ───────────────────────────────────────────────────────────────

async def get_holdings(user_id: int) -> list[dict]:
    async with get_db() as db:
        db.row_factory = _dict_factory
        async with db.execute(
            "SELECT * FROM holdings WHERE user_id = ? ORDER BY added_at",
            (user_id,),
        ) as cursor:
            return await cursor.fetchall()


async def add_holding(user_id: int, ticker: str, shares: float, buy_price: float) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT INTO holdings (user_id, ticker, shares, buy_price) VALUES (?, ?, ?, ?)",
            (user_id, ticker.upper(), shares, buy_price),
        )
        await db.commit()


async def remove_holding(holding_id: int, user_id: int) -> bool:
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM holdings WHERE id = ? AND user_id = ?",
            (holding_id, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def remove_holding_by_ticker(user_id: int, ticker: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM holdings WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )
        await db.commit()
        return cursor.rowcount > 0


# ── Alert log ──────────────────────────────────────────────────────────────

async def log_alert(user_id: int, ticker: str, alert_type: str) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT INTO alert_log (user_id, ticker, alert_type) VALUES (?, ?, ?)",
            (user_id, ticker, alert_type),
        )
        await db.commit()


async def was_alerted_today(user_id: int, ticker: str, alert_type: str) -> bool:
    async with get_db() as db:
        async with db.execute(
            """SELECT 1 FROM alert_log
               WHERE user_id = ? AND ticker = ? AND alert_type = ?
               AND date(sent_at) = date('now')""",
            (user_id, ticker, alert_type),
        ) as cursor:
            return await cursor.fetchone() is not None
