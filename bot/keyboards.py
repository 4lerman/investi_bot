from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Portfolio", callback_data="show_portfolio"),
            InlineKeyboardButton("➕ Add Stock", callback_data="add_stock"),
        ],
        [
            InlineKeyboardButton("🗑 Remove Stock", callback_data="menu_remove"),
            InlineKeyboardButton("🤖 Analyze", callback_data="analyze_portfolio"),
        ],
        [
            InlineKeyboardButton("🔔 Check Alerts", callback_data="menu_alerts"),
            InlineKeyboardButton("📅 Weekly Review", callback_data="menu_weekly"),
        ],
        [
            InlineKeyboardButton("💡 Suggestions", callback_data="menu_suggest"),
            InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
        ],
    ])


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("↩️ Main Menu", callback_data="main_menu")],
    ])


def risk_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 Low", callback_data="risk_low"),
            InlineKeyboardButton("🟡 Medium", callback_data="risk_medium"),
            InlineKeyboardButton("🔴 High", callback_data="risk_high"),
        ]
    ])


def goal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📈 Growth", callback_data="goal_growth"),
            InlineKeyboardButton("💰 Income", callback_data="goal_income"),
            InlineKeyboardButton("⚡ Short-term", callback_data="goal_short"),
        ]
    ])


def portfolio_keyboard(sort_by: str = "default") -> InlineKeyboardMarkup:
    sort_label = f"🔀 Sort: {sort_by.title()}"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Stock", callback_data="add_stock"),
            InlineKeyboardButton("🗑 Remove", callback_data="menu_remove"),
        ],
        [
            InlineKeyboardButton(sort_label, callback_data="toggle_sort"),
            InlineKeyboardButton("🤖 Analyze", callback_data="analyze_portfolio"),
        ],
        [
            InlineKeyboardButton("↩️ Main Menu", callback_data="main_menu"),
        ],
    ])


def after_alert_keyboard(ticker: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📌 Keep holding", callback_data=f"hold_{ticker}"),
            InlineKeyboardButton("✅ I'll sell", callback_data=f"sell_{ticker}"),
        ],
        [
            InlineKeyboardButton("⏰ Remind me tomorrow", callback_data=f"remind_{ticker}"),
        ],
    ])


def after_add_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 View Portfolio", callback_data="show_portfolio"),
            InlineKeyboardButton("➕ Add Another", callback_data="add_stock"),
        ],
        [
            InlineKeyboardButton("↩️ Main Menu", callback_data="main_menu"),
        ],
    ])


def remove_keyboard(holdings: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    per_page = 5
    start = page * per_page
    end = start + per_page
    page_holdings = holdings[start:end]

    buttons = []
    for h in page_holdings:
        ticker = h["ticker"]
        shares = h["shares"]
        buttons.append([
            InlineKeyboardButton(
                f"❌ {ticker} ({shares} shares)",
                callback_data=f"remove_{ticker}",
            )
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"rmpage_{page-1}"))
    if end < len(holdings):
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"rmpage_{page+1}"))

    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton("↩️ Cancel", callback_data="main_menu")])
    return InlineKeyboardMarkup(buttons)


def settings_keyboard(shariah: bool = False) -> InlineKeyboardMarkup:
    shariah_label = "☪️ Halal Mode: ON" if shariah else "☪️ Halal Mode: OFF"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💵 Change Budget", callback_data="settings_budget"),
            InlineKeyboardButton("⚖️ Change Risk", callback_data="settings_risk"),
        ],
        [
            InlineKeyboardButton("🎯 Change Goal", callback_data="settings_goal"),
            InlineKeyboardButton("🔔 Alert Threshold", callback_data="settings_alert"),
        ],
        [
            InlineKeyboardButton(shariah_label, callback_data="toggle_shariah"),
        ],
        [
            InlineKeyboardButton("↩️ Main Menu", callback_data="main_menu"),
        ],
    ])
