import logging
import warnings
from telegram import Update
from telegram.constants import ChatAction
from telegram.warnings import PTBUserWarning
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from db import queries
from core import market, claude
from core.watchlists import get_watchlist, fetch_watchlist_data
from bot import keyboards, messages

warnings.filterwarnings(
    action="ignore",
    message=r".*CallbackQueryHandler.*will not be tracked.*",
    category=PTBUserWarning,
)

logger = logging.getLogger(__name__)

# ── ConversationHandler states ─────────────────────────────────────────────
(
    SETUP_BUDGET,
    SETUP_RISK,
    ADD_TICKER,
    ADD_SHARES,
    SET_BUDGET,
    SET_ALERT,
) = range(6)


# ── Helpers ────────────────────────────────────────────────────────────────

async def _ensure_user(update: Update) -> dict:
    user = update.effective_user
    await queries.create_user(user.id, user.username or "")
    return await queries.get_user(user.id)


async def _check_analyze_limit(update: Update, user_profile: dict) -> bool:
    if user_profile.get("tier", "free") == "free" and user_profile.get("analyze_count", 0) >= 5:
        msg = "⭐️ You've used your 5 free AI queries for the week. Please upgrade or try again next Monday."
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=keyboards.back_to_menu_keyboard())
        else:
            await update.message.reply_text(msg, reply_markup=keyboards.main_menu_keyboard())
        return False
    return True


def _parse_float(text: str) -> float | None:
    try:
        value = float(text.replace(",", ".").strip())
        return value if value > 0 else None
    except ValueError:
        return None


# ── /start ─────────────────────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    existing = await queries.get_user(user.id)
    await queries.create_user(user.id, user.username or "")

    if existing:
        await update.message.reply_text(
            "Welcome back! What would you like to do?",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    await update.message.reply_text(messages.WELCOME)
    return SETUP_BUDGET


async def setup_budget_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    amount = _parse_float(update.message.text)
    if amount is None:
        await update.message.reply_text(messages.INVALID_NUMBER)
        return SETUP_BUDGET

    context.user_data["setup_budget"] = amount
    await update.message.reply_text(
        messages.ASK_RISK, reply_markup=keyboards.risk_keyboard()
    )
    return SETUP_RISK


async def setup_risk_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    risk = query.data.replace("risk_", "")
    budget = context.user_data.get("setup_budget", 95.0)
    user = query.from_user

    await queries.update_user(user.id, budget=budget, risk=risk)
    await query.edit_message_text(
        f"✅ All set! Budget: ${budget:.0f}/month, Risk: {risk}.\n\n"
        "What would you like to do?",
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END


def setup_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_handler)],
        states={
            SETUP_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_budget_received)],
            SETUP_RISK: [CallbackQueryHandler(setup_risk_callback, pattern="^risk_")],
        },
        fallbacks=[CommandHandler("start", start_handler)],
        name="setup",
        persistent=True,
    )


# ── /add ───────────────────────────────────────────────────────────────────

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_profile = await _ensure_user(update)
    if user_profile.get("tier", "free") == "free":
        holdings = await queries.get_holdings(user_profile["user_id"])
        if len(holdings) >= 5:
            msg = "⭐️ Free tier is limited to 5 stocks. Please upgrade to Premium or use /remove."
            if update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(msg, reply_markup=keyboards.back_to_menu_keyboard())
            else:
                await update.message.reply_text(msg, reply_markup=keyboards.main_menu_keyboard())
            return ConversationHandler.END

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(messages.ASK_TICKER)
    else:
        await update.message.reply_text(messages.ASK_TICKER)
    return ADD_TICKER


async def add_ticker_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ticker = update.message.text.strip().upper()
    if not ticker.isalpha() or len(ticker) > 10:
        await update.message.reply_text(messages.INVALID_TICKER)
        return ADD_TICKER

    await update.message.reply_text(f"Looking up {ticker}...")
    price = await market.get_price(ticker)
    if price is None:
        await update.message.reply_text(
            messages.PRICE_NOT_FOUND.format(ticker=ticker) + "\nTry another ticker."
        )
        return ADD_TICKER

    context.user_data["add_ticker"] = ticker
    context.user_data["add_price"] = price
    await update.message.reply_text(
        f"📈 {ticker} is currently ${price:.2f} per share.\n\n"
        f"How many shares do you want to add? (e.g. 10 or 0.5 for fractional)"
    )
    return ADD_SHARES


async def add_shares_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    shares = _parse_float(update.message.text)
    if shares is None:
        await update.message.reply_text(messages.INVALID_NUMBER)
        return ADD_SHARES

    ticker = context.user_data["add_ticker"]
    buy_price = context.user_data["add_price"]
    user_id = update.effective_user.id
    total_cost = shares * buy_price

    await queries.add_holding(user_id, ticker, shares, buy_price)

    text = (
        f"✅ Added {shares} share(s) of {ticker} at ${buy_price:.2f} each.\n"
        f"Total cost: ${total_cost:.2f}"
    )
    await update.message.reply_text(text, reply_markup=keyboards.after_add_keyboard())
    return ConversationHandler.END


async def add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def add_stock_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("add", add_start),
            CallbackQueryHandler(add_start, pattern="^add_stock$"),
        ],
        states={
            ADD_TICKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ticker_received)],
            ADD_SHARES: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_shares_received)],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
        name="add_stock",
        persistent=True,
    )


# ── /remove ────────────────────────────────────────────────────────────────

async def remove_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ensure_user(update)
    user_id = update.effective_user.id
    holdings = await queries.get_holdings(user_id)

    if not holdings:
        await update.message.reply_text(messages.EMPTY_PORTFOLIO, reply_markup=keyboards.main_menu_keyboard())
        return

    await update.message.reply_text(
        "Which stock do you want to remove?",
        reply_markup=keyboards.remove_keyboard(holdings),
    )


# ── /portfolio ─────────────────────────────────────────────────────────────

async def portfolio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_profile = await _ensure_user(update)
    user_id = user_profile["user_id"]
    holdings = await queries.get_holdings(user_id)

    if not holdings:
        await update.message.reply_text(
            messages.EMPTY_PORTFOLIO, reply_markup=keyboards.after_add_keyboard()
        )
        return

    tickers = [h["ticker"] for h in holdings]
    prices = await market.get_prices(tickers)
    
    sort_by = user_profile.get("sort_by", "default")
    text = messages.format_portfolio(holdings, prices, sort_by=sort_by)
    await update.message.reply_text(text, reply_markup=keyboards.portfolio_keyboard(sort_by=sort_by))


# ── /analyze ───────────────────────────────────────────────────────────────

async def analyze_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_profile = await _ensure_user(update)
    if not await _check_analyze_limit(update, user_profile):
        return
    user_id = update.effective_user.id
    holdings = await queries.get_holdings(user_id)

    if not holdings:
        await update.message.reply_text(messages.EMPTY_PORTFOLIO, reply_markup=keyboards.main_menu_keyboard())
        return

    await update.message.reply_text("🤖 Analyzing your portfolio...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    analysis = await claude.analyze_portfolio(holdings, user_profile)
    await queries.increment_analyze_count(user_id)
    await update.message.reply_text(analysis + messages.DISCLAIMER, reply_markup=keyboards.main_menu_keyboard())


# ── /alerts ────────────────────────────────────────────────────────────────

async def alerts_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_profile = await _ensure_user(update)
    if not await _check_analyze_limit(update, user_profile):
        return
    user_id = update.effective_user.id
    holdings = await queries.get_holdings(user_id)

    if not holdings:
        await update.message.reply_text(messages.EMPTY_PORTFOLIO, reply_markup=keyboards.main_menu_keyboard())
        return

    tickers = [h["ticker"] for h in holdings]
    prices = await market.get_prices(tickers)
    threshold = user_profile.get("alert_pct", 10.0)

    triggered = []
    for h in holdings:
        ticker = h["ticker"]
        price = prices.get(ticker)
        if price:
            drop_pct = ((h["buy_price"] - price) / h["buy_price"]) * 100
            if drop_pct >= threshold:
                triggered.append((h, price, drop_pct))

    if not triggered:
        await update.message.reply_text(messages.NO_ALERTS, reply_markup=keyboards.main_menu_keyboard())
        return

    await update.message.reply_text("🔍 Checking your alerts with AI...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    analysis = await claude.check_sell_alerts(holdings, prices, threshold)
    await queries.increment_analyze_count(user_id)

    for h, price, drop_pct in triggered:
        ticker = h["ticker"]
        text = (
            f"⚠️ SELL ALERT — {ticker}\n\n"
            f"You're down {drop_pct:.1f}% on {ticker}.\n"
            f"Your alert threshold is {threshold:.0f}%.\n\n"
            f"{analysis}"
            f"{messages.DISCLAIMER}"
        )
        await update.message.reply_text(
            text, reply_markup=keyboards.after_alert_keyboard(ticker)
        )
        await queries.log_alert(user_id, ticker, "sell")


# ── /weekly ────────────────────────────────────────────────────────────────

async def weekly_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_profile = await _ensure_user(update)
    if not await _check_analyze_limit(update, user_profile):
        return
    user_id = update.effective_user.id
    holdings = await queries.get_holdings(user_id)

    if not holdings:
        await update.message.reply_text(messages.EMPTY_PORTFOLIO, reply_markup=keyboards.main_menu_keyboard())
        return

    tickers = [h["ticker"] for h in holdings]
    prices = await market.get_prices(tickers)

    await update.message.reply_text("📅 Generating your weekly review...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    review = await claude.generate_weekly_review(holdings, prices, user_profile)
    await queries.increment_analyze_count(user_id)
    await update.message.reply_text(review + messages.DISCLAIMER, reply_markup=keyboards.main_menu_keyboard())


# ── /suggest ───────────────────────────────────────────────────────────────

async def suggest_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_profile = await _ensure_user(update)
    if not await _check_analyze_limit(update, user_profile):
        return
    user_id = update.effective_user.id
    holdings = await queries.get_holdings(user_id)
    budget = user_profile.get("budget", 95.0)
    shariah = bool(user_profile.get("shariah", 0))

    holding_tickers = [h["ticker"] for h in holdings]
    prices = await market.get_prices(holding_tickers) if holding_tickers else {}

    # Fetch watchlist data with real market prices
    watchlist = get_watchlist(shariah=shariah)
    watchlist_data = await fetch_watchlist_data(watchlist, exclude_tickers=holding_tickers)

    await update.message.reply_text("💡 Generating buy suggestions...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    suggestions = await claude.generate_buy_suggestions(
        holdings, user_profile, budget, prices,
        watchlist_data=watchlist_data,
    )
    await queries.increment_analyze_count(user_id)

    # Prices already available from watchlist data
    suggestion_prices = {t: info["price"] for t, info in watchlist_data.items()}

    text = messages.format_suggestions(suggestions, budget, suggestion_prices)
    await update.message.reply_text(text, reply_markup=keyboards.main_menu_keyboard())


# ── /settings ─────────────────────────────────────────────────────────────

async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_profile = await _ensure_user(update)
    shariah = bool(user_profile.get("shariah", 0))
    shariah_text = "ON (halal ETFs only)" if shariah else "OFF"
    text = (
        f"⚙️ Your Settings\n\n"
        f"Monthly budget: ${user_profile.get('budget', 95):.0f}\n"
        f"Risk tolerance: {user_profile.get('risk', 'medium')}\n"
        f"Goal: {user_profile.get('goal', 'growth')}\n"
        f"Sell-alert threshold: {user_profile.get('alert_pct', 10):.0f}%\n"
        f"Halal mode: {shariah_text}"
    )
    await update.message.reply_text(text, reply_markup=keyboards.settings_keyboard(shariah=shariah))


# ── /budget ────────────────────────────────────────────────────────────────

async def budget_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _ensure_user(update)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(messages.ASK_BUDGET)
    else:
        await update.message.reply_text(messages.ASK_BUDGET)
    return SET_BUDGET


async def budget_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    amount = _parse_float(update.message.text)
    if amount is None:
        await update.message.reply_text(messages.INVALID_NUMBER)
        return SET_BUDGET

    user_id = update.effective_user.id
    await queries.update_user(user_id, budget=amount)
    await update.message.reply_text(
        messages.BUDGET_SAVED.format(budget=amount),
        reply_markup=keyboards.main_menu_keyboard()
    )
    return ConversationHandler.END


def budget_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("budget", budget_start),
            CallbackQueryHandler(budget_start, pattern="^settings_budget$"),
        ],
        states={
            SET_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget_received)],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
        name="set_budget",
        persistent=True,
    )


# ── /alert ────────────────────────────────────────────────────────────────

async def alert_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _ensure_user(update)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(messages.ASK_ALERT_PCT)
    else:
        await update.message.reply_text(messages.ASK_ALERT_PCT)
    return SET_ALERT


async def alert_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pct = _parse_float(update.message.text)
    if pct is None:
        await update.message.reply_text(messages.INVALID_NUMBER)
        return SET_ALERT

    user_id = update.effective_user.id
    await queries.update_user(user_id, alert_pct=pct)
    await update.message.reply_text(
        messages.ALERT_SAVED.format(pct=pct),
        reply_markup=keyboards.main_menu_keyboard()
    )
    return ConversationHandler.END


def alert_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("alert", alert_start),
            CallbackQueryHandler(alert_start, pattern="^settings_alert$"),
        ],
        states={
            SET_ALERT: [MessageHandler(filters.TEXT & ~filters.COMMAND, alert_received)],
        },
        fallbacks=[CommandHandler("cancel", add_cancel)],
        name="set_alert",
        persistent=True,
    )


# ── /risk ──────────────────────────────────────────────────────────────────

async def risk_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ensure_user(update)
    await update.message.reply_text(messages.ASK_RISK, reply_markup=keyboards.risk_keyboard())


# ── /shariah ───────────────────────────────────────────────────────────────

async def shariah_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_profile = await _ensure_user(update)
    current = bool(user_profile.get("shariah", 0))
    new_value = 0 if current else 1
    await queries.update_user(update.effective_user.id, shariah=new_value)

    if new_value:
        text = (
            "☪️ Halal mode is now ON.\n"
            "Buy suggestions will only include Shariah-compliant ETFs "
            "(SPUS, HLAL, UMMA, etc.)."
        )
    else:
        text = (
            "☪️ Halal mode is now OFF.\n"
            "Buy suggestions will use the general ETF watchlist."
        )
    await update.message.reply_text(text, reply_markup=keyboards.main_menu_keyboard())


# ── /help ──────────────────────────────────────────────────────────────────

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        messages.HELP, reply_markup=keyboards.main_menu_keyboard()
    )


# ── Inline callback router ─────────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("risk_"):
        risk = data.replace("risk_", "")
        user_id = query.from_user.id
        await queries.update_user(user_id, risk=risk)
        await query.edit_message_text(messages.RISK_SAVED.format(risk=risk))

    elif data.startswith("goal_"):
        goal = data.replace("goal_", "")
        user_id = query.from_user.id
        await queries.update_user(user_id, goal=goal)
        await query.edit_message_text(messages.GOAL_SAVED.format(goal=goal))

    elif data == "show_portfolio":
        user_id = query.from_user.id
        user_profile = await queries.get_user(user_id)
        holdings = await queries.get_holdings(user_id)
        if not holdings:
            await query.edit_message_text(messages.EMPTY_PORTFOLIO, reply_markup=keyboards.main_menu_keyboard())
            return
        prices = await market.get_prices([h["ticker"] for h in holdings])
        
        sort_by = user_profile.get("sort_by", "default")
        text = messages.format_portfolio(holdings, prices, sort_by=sort_by)
        await query.edit_message_text(text, reply_markup=keyboards.portfolio_keyboard(sort_by=sort_by))

    elif data == "toggle_sort":
        user_id = query.from_user.id
        user_profile = await queries.get_user(user_id)
        current_sort = user_profile.get("sort_by", "default")
        sort_modes = ["default", "value", "performance"]
        try:
            next_idx = (sort_modes.index(current_sort) + 1) % len(sort_modes)
        except ValueError:
            next_idx = 1
        new_sort = sort_modes[next_idx]
        
        await queries.update_user(user_id, sort_by=new_sort)
        
        holdings = await queries.get_holdings(user_id)
        if not holdings:
            await query.answer("Empty portfolio.")
            return
        prices = await market.get_prices([h["ticker"] for h in holdings])
        
        text = messages.format_portfolio(holdings, prices, sort_by=new_sort)
        await query.edit_message_text(text, reply_markup=keyboards.portfolio_keyboard(sort_by=new_sort))

    elif data == "analyze_portfolio":
        user_id = query.from_user.id
        user_profile = await queries.get_user(user_id)
        if not await _check_analyze_limit(update, user_profile):
            return
        holdings = await queries.get_holdings(user_id)
        if not holdings:
            await query.edit_message_text(messages.EMPTY_PORTFOLIO, reply_markup=keyboards.main_menu_keyboard())
            return
        await query.edit_message_text("🤖 Analyzing your portfolio...")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        analysis = await claude.analyze_portfolio(holdings, user_profile)
        await queries.increment_analyze_count(user_id)
        await query.edit_message_text(
            analysis + messages.DISCLAIMER,
            reply_markup=keyboards.back_to_menu_keyboard(),
        )

    elif data.startswith("rmpage_"):
        try:
            page = int(data.replace("rmpage_", ""))
        except ValueError:
            page = 0
        user_id = query.from_user.id
        holdings = await queries.get_holdings(user_id)
        if holdings:
            await query.edit_message_reply_markup(
                reply_markup=keyboards.remove_keyboard(holdings, page)
            )

    elif data.startswith("remove_"):
        ticker = data.replace("remove_", "")
        user_id = query.from_user.id
        removed = await queries.remove_holding_by_ticker(user_id, ticker)
        if removed:
            await query.edit_message_text(
                messages.HOLDING_REMOVED.format(ticker=ticker),
                reply_markup=keyboards.back_to_menu_keyboard(),
            )
        else:
            await query.edit_message_text(
                messages.HOLDING_NOT_FOUND.format(ticker=ticker),
                reply_markup=keyboards.back_to_menu_keyboard(),
            )

    elif data.startswith("hold_"):
        ticker = data.replace("hold_", "")
        await query.edit_message_text(
            f"📌 Noted — keeping {ticker} for now. Check back later!",
            reply_markup=keyboards.back_to_menu_keyboard(),
        )

    elif data.startswith("sell_"):
        ticker = data.replace("sell_", "")
        await query.edit_message_text(
            f"✅ Good decision to review {ticker}. "
            f"Use /remove to remove it once you've sold.",
            reply_markup=keyboards.back_to_menu_keyboard(),
        )

    elif data.startswith("remind_"):
        ticker = data.replace("remind_", "")
        await query.edit_message_text(
            f"⏰ I'll check {ticker} again in tomorrow's daily alert.",
            reply_markup=keyboards.back_to_menu_keyboard(),
        )

    elif data == "settings_risk":
        await query.edit_message_text(
            messages.ASK_RISK, reply_markup=keyboards.risk_keyboard()
        )

    elif data == "settings_goal":
        await query.edit_message_text(
            messages.ASK_GOAL, reply_markup=keyboards.goal_keyboard()
        )

    elif data == "toggle_shariah":
        user_id = query.from_user.id
        user_profile = await queries.get_user(user_id)
        current = bool(user_profile.get("shariah", 0))
        new_value = 0 if current else 1
        await queries.update_user(user_id, shariah=new_value)

        status = "ON — suggestions will use Shariah-compliant ETFs only" if new_value else "OFF — using general ETF watchlist"
        await query.edit_message_text(
            f"☪️ Halal mode: {status}",
            reply_markup=keyboards.settings_keyboard(shariah=bool(new_value)),
        )

    elif data == "main_menu":
        await query.edit_message_text(
            "What would you like to do?",
            reply_markup=keyboards.main_menu_keyboard(),
        )

    elif data == "menu_remove":
        user_id = query.from_user.id
        holdings = await queries.get_holdings(user_id)
        if not holdings:
            await query.edit_message_text(
                messages.EMPTY_PORTFOLIO,
                reply_markup=keyboards.back_to_menu_keyboard(),
            )
            return
        await query.edit_message_text(
            "Which stock do you want to remove?",
            reply_markup=keyboards.remove_keyboard(holdings),
        )

    elif data == "menu_alerts":
        user_id = query.from_user.id
        user_profile = await queries.get_user(user_id)
        if not await _check_analyze_limit(update, user_profile):
            return
        holdings = await queries.get_holdings(user_id)
        if not holdings:
            await query.edit_message_text(
                messages.EMPTY_PORTFOLIO,
                reply_markup=keyboards.back_to_menu_keyboard(),
            )
            return
        await query.edit_message_text("🔍 Checking your alerts...")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        tickers = [h["ticker"] for h in holdings]
        prices = await market.get_prices(tickers)
        threshold = user_profile.get("alert_pct", 10.0)
        triggered = []
        for h in holdings:
            ticker = h["ticker"]
            price = prices.get(ticker)
            if price:
                drop_pct = ((h["buy_price"] - price) / h["buy_price"]) * 100
                if drop_pct >= threshold:
                    triggered.append((h, price, drop_pct))
        if not triggered:
            await query.edit_message_text(
                messages.NO_ALERTS,
                reply_markup=keyboards.back_to_menu_keyboard(),
            )
            return
        analysis = await claude.check_sell_alerts(holdings, prices, threshold)
        await queries.increment_analyze_count(user_id)
        alert_texts = []
        for h, price, drop_pct in triggered:
            alert_texts.append(
                f"⚠️ {h['ticker']} — down {drop_pct:.1f}%"
            )
            await queries.log_alert(user_id, h["ticker"], "sell")
        text = "\n".join(alert_texts) + f"\n\n{analysis}{messages.DISCLAIMER}"
        await query.edit_message_text(
            text, reply_markup=keyboards.back_to_menu_keyboard()
        )

    elif data == "menu_weekly":
        user_id = query.from_user.id
        user_profile = await queries.get_user(user_id)
        if not await _check_analyze_limit(update, user_profile):
            return
        holdings = await queries.get_holdings(user_id)
        if not holdings:
            await query.edit_message_text(
                messages.EMPTY_PORTFOLIO,
                reply_markup=keyboards.back_to_menu_keyboard(),
            )
            return
        await query.edit_message_text("📅 Generating your weekly review...")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        tickers = [h["ticker"] for h in holdings]
        prices = await market.get_prices(tickers)
        review = await claude.generate_weekly_review(holdings, prices, user_profile)
        await queries.increment_analyze_count(user_id)
        await query.edit_message_text(
            review + messages.DISCLAIMER,
            reply_markup=keyboards.back_to_menu_keyboard(),
        )

    elif data == "menu_suggest":
        user_id = query.from_user.id
        user_profile = await queries.get_user(user_id)
        if not await _check_analyze_limit(update, user_profile):
            return
        holdings = await queries.get_holdings(user_id)
        budget = user_profile.get("budget", 95.0)
        shariah = bool(user_profile.get("shariah", 0))
        await query.edit_message_text("💡 Generating buy suggestions...")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        holding_tickers = [h["ticker"] for h in holdings]
        prices = await market.get_prices(holding_tickers) if holding_tickers else {}
        watchlist = get_watchlist(shariah=shariah)
        watchlist_data = await fetch_watchlist_data(watchlist, exclude_tickers=holding_tickers)
        suggestions = await claude.generate_buy_suggestions(
            holdings, user_profile, budget, prices,
            watchlist_data=watchlist_data,
        )
        await queries.increment_analyze_count(user_id)
        suggestion_prices = {t: info["price"] for t, info in watchlist_data.items()}
        text = messages.format_suggestions(suggestions, budget, suggestion_prices)
        await query.edit_message_text(
            text, reply_markup=keyboards.back_to_menu_keyboard()
        )

    elif data == "menu_settings":
        user_id = query.from_user.id
        user_profile = await queries.get_user(user_id)
        shariah = bool(user_profile.get("shariah", 0))
        shariah_text = "ON (halal ETFs only)" if shariah else "OFF"
        text = (
            f"⚙️ Your Settings\n\n"
            f"Monthly budget: ${user_profile.get('budget', 95):.0f}\n"
            f"Risk tolerance: {user_profile.get('risk', 'medium')}\n"
            f"Goal: {user_profile.get('goal', 'growth')}\n"
            f"Sell-alert threshold: {user_profile.get('alert_pct', 10):.0f}%\n"
            f"Halal mode: {shariah_text}"
        )
        await query.edit_message_text(
            text, reply_markup=keyboards.settings_keyboard(shariah=shariah)
        )
