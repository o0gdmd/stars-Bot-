import logging
import os
import sqlite3
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# States
ADD_STARS_STATE, WITHDRAW_AMOUNT_STATE, SET_WALLET_STATE = range(3)

# --- Database functions ---
def init_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            ton_wallet TEXT,
            total_deposits INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    data = cursor.fetchone()
    if not data:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        data = (user_id, 0, None, 0)
    conn.close()
    return {"user_id": data[0], "balance": data[1], "ton_wallet": data[2], "total_deposits": data[3]}

def update_user_data(user_id, **kwargs):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    for key, value in kwargs.items():
        cursor.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

# --- VIP System ---
def get_vip_level(total_deposits):
    if total_deposits >= 150000:
        return "VIP 5"
    elif total_deposits >= 100000:
        return "VIP 4"
    elif total_deposits >= 50000:
        return "VIP 3"
    elif total_deposits >= 20000:
        return "VIP 2"
    elif total_deposits >= 10000:
        return "VIP 1"
    else:
        return "VIP 0"

# --- Welcome Message ---
async def welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_info = get_user_data(user_id)
    total_deposits = user_info.get("total_deposits", 0)
    vip_level = get_vip_level(total_deposits)

    message = (
        "⭐️ STARS WALLET VIP SYSTEM ⭐️\n"
        f"💫 Your Status:\n"
        f"➖ Current Level: {vip_level}\n"
        f"➖ Total Deposits: {total_deposits} ⭐\n"
        f"➖ Unlock Period: 5 days\n"
        "🔥 Next Level:\n"
        f"➖ Need {max(10000 - total_deposits,0)} more ⭐ for ⭐ VIP 1\n"
        "📊 VIP LEVELS & BENEFITS 📊\n"
        "🆕 VIP 0\n➖ Range: 1000 - 9,999 ⭐\n➖ Unlock Period: 5 days\n"
        "⭐ VIP 1\n➖ Range: 10,000 - 19,999 ⭐\n➖ Unlock Period: 4 days\n"
        "⭐⭐ VIP 2\n➖ Range: 20,000 - 49,999 ⭐\n➖ Unlock Period: 3 days\n"
        "⭐⭐⭐ VIP 3\n➖ Range: 50,000 - 99,999 ⭐\n➖ Unlock Period: 2 days\n"
        "💎 VIP 4\n➖ Range: 100,000 - 149,999 ⭐\n➖ Unlock Period: 1 days\n"
        "👑 VIP 5\n➖ Range: 150,000+ ⭐\n➖ Unlock Period: Instant Withdrawal\n"
        "\n📝 Note: VIP level is calculated based on total deposits"
    )
    await update.message.reply_text(message)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_user_data(user_id)

    # Show welcome message first
    await welcome_message(update, context)

    menu_keyboard = [
        [KeyboardButton("➕ Add Funds"), KeyboardButton("🏧 Withdraw")],
        [KeyboardButton("👤 Account"), KeyboardButton("👛 Wallet")]
    ]
    reply_markup = ReplyKeyboardMarkup(menu_keyboard, resize_keyboard=True)

    await update.message.reply_text("Welcome! Choose an option:", reply_markup=reply_markup)

async def account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_info = get_user_data(user.id)

    wallet_address = user_info["ton_wallet"] if user_info["ton_wallet"] else "Not set"
    total_deposits = user_info.get("total_deposits", 0)
    vip_level = get_vip_level(total_deposits)

    response_text = (
        f"👤 Your Account:\n"
        f"- ID: {user.id}\n"
        f"- Username: @{user.username}\n"
        f"- Balance: {user_info['balance']} Stars\n"
        f"- TON Wallet: {wallet_address}\n"
        f"- VIP Level: {vip_level}\n"
        f"- Total Deposits: {total_deposits} Stars"
    )
    await update.message.reply_text(response_text)

# --- Add Funds ---
async def add_fund_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Enter the number of Stars you want to add (min: 100):")
    return ADD_STARS_STATE

async def get_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        stars_amount = int(update.message.text)
        if stars_amount < 100:
            await update.message.reply_text("Minimum is 100 Stars. Enter a valid number:")
            return ADD_STARS_STATE

        bot_username = context.bot.username
        pay_url = f"https://t.me/{bot_username}?startattach=pay&amount={stars_amount}&currency=XTR"

        keyboard = [[InlineKeyboardButton(f"Pay {stars_amount} Stars", url=pay_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Click the button below to pay {stars_amount} Stars:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Invalid input. Enter a number:")
        return ADD_STARS_STATE

# --- Withdraw ---
async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Enter the amount of Stars you want to withdraw:")
    return WITHDRAW_AMOUNT_STATE

async def handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_info = get_user_data(user_id)

    try:
        amount = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Invalid input. Enter a number:")
        return WITHDRAW_AMOUNT_STATE

    if amount <= 0:
        await update.message.reply_text("Enter a number greater than 0:")
        return WITHDRAW_AMOUNT_STATE

    if amount > user_info["balance"]:
        await update.message.reply_text("You don’t have enough balance.")
        return WITHDRAW_AMOUNT_STATE

    context.user_data["withdraw_amount"] = amount
    keyboard = [[InlineKeyboardButton("✅ Confirm Withdraw", callback_data="confirm_withdraw")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"You requested to withdraw {amount} Stars.\nClick confirm to proceed.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_info = get_user_data(user_id)

    amount = context.user_data.get("withdraw_amount")
    if not amount:
        await query.edit_message_text("No withdrawal request found.")
        return

    if amount > user_info["balance"]:
        await query.edit_message_text("Insufficient balance.")
        return

    new_balance = user_info["balance"] - amount
    update_user_data(user_id, balance=new_balance)

    await query.edit_message_text(
        f"✅ Withdrawal request of {amount} Stars has been received.\n"
        f"Remaining balance: {new_balance} Stars.\n"
        f"Your TON will be sent soon."
    )

# --- Wallet ---
async def wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_info = get_user_data(update.effective_user.id)
    current_wallet = user_info["ton_wallet"] if user_info["ton_wallet"] else "Not set"
    await update.message.reply_text(
        f"Your current TON wallet: `{current_wallet}`\nSend me your new TON wallet address:",
        parse_mode="Markdown"
    )
    return SET_WALLET_STATE

async def set_ton_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    new_wallet = update.message.text

    if not (new_wallet.startswith(("EQ", "UQ")) or new_wallet.endswith((".ton",))):
        await update.message.reply_text("Invalid TON wallet address. Try again:")
        return SET_WALLET_STATE

    update_user_data(user_id, ton_wallet=new_wallet)
    await update.message.reply_text(
        f"✅ Your TON wallet has been updated!\nCurrent wallet: `{new_wallet}`",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# --- Handle Stars Payment ---
async def star_transaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.star_transaction:
        star_transaction = update.star_transaction
        user_id = star_transaction.payer.id
        amount = star_transaction.amount

        if star_transaction.type == "StarsPayment":
            user_info = get_user_data(user_id)
            new_balance = user_info["balance"] + amount
            new_total = user_info["total_deposits"] + amount
            update_user_data(user_id, balance=new_balance, total_deposits=new_total)

            await context.bot.send_message(
                chat_id=user_id,
                text=f"✅ Payment received: {amount} Stars\nYour new balance: {new_balance} Stars"
            )

# --- Main ---
def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    add_fund_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Add Funds$"), add_fund_start)],
        states={ADD_STARS_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_stars_amount)]},
        fallbacks=[CommandHandler("cancel", start)],
    )

    withdraw_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🏧 Withdraw$"), withdraw_handler)],
        states={WITHDRAW_AMOUNT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)]},
        fallbacks=[CommandHandler("cancel", start)],
    )

    wallet_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👛 Wallet$"), wallet_start)],
        states={SET_WALLET_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_ton_wallet)]},
        fallbacks=[CommandHandler("cancel", start)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^👤 Account$"), account_handler))
    application.add_handler(add_fund_conv)
    application.add_handler(withdraw_conv)
    application.add_handler(wallet_conv)
    application.add_handler(CallbackQueryHandler(confirm_withdrawal, pattern="^confirm_withdraw$"))
    application.add_handler(MessageHandler(filters.ALL, star_transaction_handler))

    PORT = int(os.environ.get("PORT", 8080))
    URL = os.environ.get("RENDER_EXTERNAL_URL", "https://your-render-app-name.onrender.com")

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{URL}/{BOT_TOKEN}"
    )
    logging.info(f"Webhook started at {URL}:{PORT}")

if __name__ == "__main__":
    main()
