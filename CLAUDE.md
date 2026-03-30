# invest_bot

Telegram bot that manages an investment portfolio with AI-powered analysis via Groq (Llama 3.3 70B).

## Tech Stack

- **Python 3.13** (async throughout), venv at `.venv/`
- **python-telegram-bot 21.6** — async Telegram framework
- **aiosqlite** — async SQLite persistence
- **yfinance** — live stock prices (5-day history, 15-min cache TTL)
- **Groq SDK** — free LLM API (llama-3.3-70b-versatile)
- **APScheduler** — cron-based scheduled jobs
- **python-dotenv** — env config

## Project Structure

```
main.py              # Entry point, PTB post_init pattern
.env                 # TELEGRAM_BOT_TOKEN, GROQ_API_KEY, DATABASE_PATH
data/                # SQLite DB (auto-created)
db/
  database.py        # DB init, get_db() returns aiosqlite.connect()
  queries.py         # CRUD with _dict_factory for row→dict
core/
  market.py          # get_price(), get_prices() with 15-min TTL cache
  claude.py          # LLM: analyze_portfolio, check_sell_alerts, generate_weekly_review, generate_buy_suggestions
  alerts.py          # Daily sell alert logic
  scheduler.py       # 3 scheduled jobs: daily alerts, weekly reviews, monthly suggestions
bot/
  handlers.py        # All command handlers (/start, /add, /remove, /portfolio, /analyze, /alerts, /weekly, /suggest, /settings, /budget, /risk)
  keyboards.py       # Inline keyboards including remove_keyboard()
  messages.py        # Message templates and formatters
```

## Setup & Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Environment Variables (`.env`)

- `TELEGRAM_BOT_TOKEN` — from BotFather
- `GROQ_API_KEY` — from console.groq.com
- `DATABASE_PATH` — path to SQLite DB (default: `./data/investment_bot.db`)

## Key Patterns

- `main.py` uses PTB's `post_init` callback for async init (DB + scheduler), then `app.run_polling()` from sync `main()`
- `get_db()` is **sync**, returns `aiosqlite.connect()` as context manager (use with `async with`)
- `_dict_factory` in `queries.py` converts rows to dicts
- `_call_llm()` in `claude.py` uses `asyncio.to_thread()` to wrap sync Groq client
- `/add` auto-fetches price via yfinance, asks only ticker + shares
- `/remove` shows inline keyboard buttons for holdings
- `/suggest` and `send_monthly_suggestions()` use two-phase price fetching: (1) existing holdings before LLM call, (2) suggested tickers after LLM call

## Scheduled Jobs

- **Daily alerts** — weekdays 14:30 UTC (sell alert checks)
- **Weekly reviews** — Sundays 10:00 UTC
- **Monthly suggestions** — 1st of month 09:00 UTC

## Past Issues (Resolved)

- Used `post_init` pattern to avoid "event loop already running" error
- `get_db()` changed from async to sync to fix "thread can only be started once"
- Added `_dict_factory` to fix `dict(row)` TypeError with aiosqlite
- Simplified yfinance to `history(period="5d")` to handle rate limiting
- Switched from Anthropic (paid) to Groq (free) for LLM backend

## Current State

- `GROQ_API_KEY` in `.env` may need to be set — last test got 401 Invalid API Key
- No test suite; manual testing only (see SPECIFICATION.md for test scenarios)
- Logging goes to `bot.log` and console (INFO level)

## Future Scaling & Improvements (V2.0)

When moving beyond the initial deployment and scaling to handle more users or complex features, track these architectural upgrades:

### 1. Infrastructure & Deployment
- **Webhooks Migration**: Move away from `app.run_polling()` to Webhooks so that Telegram pushes updates to the server. This is more efficient under load.
- **Dockerization**: Containerize the bot using a `Dockerfile` and `docker-compose.yml`, mounting a volume for `bot_state.pickle` and the aiosqlite database to ensure painless server migrations.

### 2. Performance & Rate Limiting
- **Market Data Caching**: Implement in-memory caching (e.g., Redis or simply tracking TTL limits) specifically for `yfinance` to prevent API rate limits when multiple users query the same stock (like AAPL) simultaneously.
- **LLM Request Queueing**: If user traffic spikes, `Groq` API usage may hit global RPM (Requests Per Minute) limits. Introduce a background task queue (like Celery or RQ) to queue `/analyze` requests and process them sequentially without dropping user inputs.

### 3. Database Evolution
- **PostgreSQL Migration**: `aiosqlite` locks the database on writes. As concurrent users increase and portfolio modifications happen simultaneously, migrate to PostgreSQL (using `asyncpg` or `SQLAlchemy`) to handle high-concurrency writes natively.

### 4. Monetization & Premium Tiers
- **Telegram Native Payments**: Use Telegram's built-in payment API (or Telegram Stars) attached to an `/upgrade` slash command. This will allow users to unlock premium tier database features (e.g., unlimited tracked stocks and deeper analysis insights).
