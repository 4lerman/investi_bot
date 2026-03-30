import os
import aiosqlite
from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/investment_bot.db")


def get_db() -> aiosqlite.Connection:
    """Return an aiosqlite connection context manager. Use with `async with`."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    return aiosqlite.connect(DATABASE_PATH)


async def init_db() -> None:
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id       INTEGER PRIMARY KEY,
                username      TEXT,
                risk          TEXT DEFAULT 'medium',
                goal          TEXT DEFAULT 'growth',
                sectors       TEXT DEFAULT '',
                budget        REAL DEFAULT 95.0,
                alert_pct     REAL DEFAULT 10.0,
                shariah       INTEGER DEFAULT 0,
                analyze_count INTEGER DEFAULT 0,
                tier          TEXT DEFAULT 'free',
                sort_by       TEXT DEFAULT 'default',
                created_at    TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS holdings (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                ticker        TEXT NOT NULL,
                shares        REAL NOT NULL,
                buy_price     REAL NOT NULL,
                added_at      TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS alert_log (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL,
                ticker        TEXT NOT NULL,
                alert_type    TEXT NOT NULL,
                sent_at       TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Migration for existing databases: add shariah column if missing
        try:
            await db.execute("ALTER TABLE users ADD COLUMN shariah INTEGER DEFAULT 0")
        except Exception:
            pass  # column already exists
        try:
            await db.execute("ALTER TABLE users ADD COLUMN analyze_count INTEGER DEFAULT 0")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN tier TEXT DEFAULT 'free'")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN sort_by TEXT DEFAULT 'default'")
        except Exception:
            pass
        await db.commit()
