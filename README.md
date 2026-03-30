# Invest Bot 📈🤖

An asynchronous Telegram bot that manages an investment portfolio with AI-powered analysis via Groq (Llama 3.3 70B). The bot provides live stock pricing, custom alerts, weekly portfolio performance reviews, and intelligent buy suggestions tailored to your budget and risk tolerance.

## 🌟 Features

* **Portfolio Management**: Add, remove, and track live valuations of your stocks.
* **AI Portfolio Analysis**: Get deep insights on your diversification and position strength via Llama 3.3 70B.
* **Smart Alerts**: Set custom drop-percentage thresholds to receive daily notifications if a stock underperforms.
* **Weekly Automated Reviews**: Receive detailed portfolio performance recaps directly in Telegram every Sunday.
* **Monthly Buy Suggestions**: Get personalized asset suggestions on the 1st of every month based on your risk tolerance, free capital, and halal mode settings.
* **Zero CLI Friction**: Fully button-driven UI flow for seamless, one-tap usage.

## 🛠 Tech Stack

* **Python 3.13** (Fully Async)
* **python-telegram-bot (v21.6)** — Event-driven UI framework with state persistence
* **aiosqlite** — Asynchronous SQLite persistence
* **yfinance** — Live market prices (with built-in 15-minute TTL caching)
* **Groq SDK** — Blazing fast LLM inference (llama-3.3-70b-versatile)
* **APScheduler** — Cron-based scheduled background jobs
* **pytest & pytest-asyncio** — Automated testing suite

## 🚀 Setup & Installation

**Prerequisites:** Python 3.13

1. **Clone the repository:**
   ```bash
   git clone https://github.com/4lerman/investi_bot.git
   cd investi_bot
   ```

2. **Set up the virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory (or rename `.env.example`):
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_from_botfather
   GROQ_API_KEY=your_groq_api_key_from_console.groq.com
   DATABASE_PATH=data/investment_bot.db
   ```

5. **Run the bot:**
   ```bash
   python main.py
   ```

## 🧪 Testing

The test suite ensures robust parsing, caching, and database queries. Run tests locally using:
```bash
pytest tests/
```

## 🔮 Future Improvements (V2 Roadmap)
- Migration from standard polling to Webhooks for high-scale environments
- Full Dockerization for seamless deployment
- PostgreSQL migration to support heavy concurrent read/writes
- Telegram Native Payments to support premium-tier usage limits

## ⚠️ Disclaimer
All generated insights and buy suggestions from this bot are purely for educational purposes and do **not** constitute financial advice.
