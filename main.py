import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, LabeledPrice
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters, PreCheckoutQueryHandler
)

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DATABASE_URL = os.environ.get("DATABASE_URL")

# States
ADD_STARS_STATE, WITHDRAW_AMOUNT_STATE, SET_WALLET_STATE = range(3)

# --- Database functions ---
def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            balance BIGINT DEFAULT 0,
            ton_wallet TEXT,
            total_deposits BIGINT DEFAULT 0
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

def get_user_data(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    data = cursor.fetchone()
    if not data:
        cursor.execute("INSERT INTO users (user_id) VALUES (%s)", (user_id,))
        conn.commit()
        data = {"user_id": user_id, "balance": 0, "ton_wallet": None, "total_deposits": 0}
    cursor.close()
    conn.close()
    return data

def update_user_data(user_id, **kwargs):
    conn = get_connection()
    cursor = conn.cursor()
    for key, value in kwargs.items():
        cursor.execute(f"UPDATE users SET {key} = %s WHERE user_id = %s", (value, user_id))
    conn.commit()
    cursor.close()
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

# --- Start Handler ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start message with main menu buttons only."""
    user_id = update.effective_user.id
    get_user_data(user_id)

    # Main menu keyboard
    menu_keyboard = [
        [KeyboardButton("➕ Add Funds"), KeyboardButton("🏧 Withdraw")],
        [KeyboardButton("👤 Account"), KeyboardButton("👛 Wallet")]
    ]
    reply_markup = ReplyKeyboardMarkup(menu_keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Please choose an option from below:", 
        reply_markup=reply_markup
    )

# --- Cancel Keyboard ---
def cancel_keyboard():
    """Returns a keyboard with only Cancel button."""
    return ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel")]], resize_keyboard=True)

# --- Account ---
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

# --- Add Funds with Telegram Stars ---
async def add_fund_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Enter the number of Stars you want to add (min: 100):"
    )
    return ADD_STARS_STATE

async def get_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        stars_amount = int(update.message.text)
        if stars_amount < 100:
            await update.message.reply_text("Minimum is 100 Stars. Enter a valid number:")
            return ADD_STARS_STATE

        prices = [LabeledPrice("Stars", stars_amount)]
        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title="Buy Stars",
            description=f"Adding {stars_amount} Stars to your balance",
            payload=str(stars_amount),
            provider_token="",
            currency="XTR",
            prices=prices
        )
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Invalid input. Enter a number:")
        return ADD_STARS_STATE

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

    # رسالة التأكيد ثم العودة تلقائيًا للأزرار الرئيسية
    await update.message.reply_text(
        f"✅ Your TON wallet has been updated successfully!\nCurrent wallet: `{new_wallet}`",
        parse_mode="Markdown"
    )
    await start(update, context)
    return ConversationHandler.END

# --- Star Transactions fallback ---
async def star_transaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if getattr(update, "star_transaction", None):
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

# --- Handle Cancel ---
async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)
    return ConversationHandler.END

# --- Main ---
def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    add_fund_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Add Funds$"), add_fund_start)],
        states={ADD_STARS_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_stars_amount)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), handle_cancel)],
    )

    withdraw_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🏧 Withdraw$"), withdraw_handler)],
        states={WITHDRAW_AMOUNT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), handle_cancel)],
    )

    wallet_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👛 Wallet$"), wallet_start)],
        states={SET_WALLET_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_ton_wallet)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), handle_cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^👤 Account$"), account_handler))
    application.add_handler(add_fund_conv)
    application.add_handler(withdraw_conv)
    application.add_handler(wallet_conv)
    application.add_handler(CallbackQueryHandler(confirm_withdrawal, pattern="^confirm_withdraw$"))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    application.add_handler(PreCheckoutQueryHandler(precheckout_handler))
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
