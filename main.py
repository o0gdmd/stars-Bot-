import logging
import os
import psycopg2
import json
import hashlib
import hmac
import asyncio
from psycopg2.extras import RealDictCursor
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, LabeledPrice
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters, PreCheckoutQueryHandler
)
from flask import Flask, jsonify, request, send_from_directory

# --- Flask App ---
app = Flask(__name__)

# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6172153716"))
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://your-render-app-name.onrender.com")

# --- States ---
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS start_users (
            user_id BIGINT PRIMARY KEY
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

# --- Keyboards ---
def main_menu_keyboard_with_miniapp():
    return ReplyKeyboardMarkup([
        [KeyboardButton("➕ Add Funds"), KeyboardButton("🏧 Withdraw")],
        [
            KeyboardButton("👤 Account"),
            KeyboardButton("Launch Mini App 🚀", web_app={"url": f"{RENDER_URL}/miniapp/index.html"})
        ]
    ], resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel")]], resize_keyboard=True)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_user_data(user_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO start_users (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    await update.message.reply_text(
        "Please choose an option from below:", 
        reply_markup=main_menu_keyboard_with_miniapp()
    )

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) AS count FROM start_users")
    count = cursor.fetchone()["count"]
    cursor.close()
    conn.close()
    await update.message.reply_text(f"📈 Number of unique users who pressed /start: {count}")

async def account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_info = get_user_data(user.id)
    wallet_address = user_info["ton_wallet"] or "Not set"
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

async def add_fund_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Enter the number of Stars you want to add (min: 100):",
        reply_markup=cancel_keyboard()
    )
    return ADD_STARS_STATE

async def get_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Cancel":
        await start(update, context)
        return ConversationHandler.END
    try:
        stars_amount = int(update.message.text)
        if stars_amount < 100:
            await update.message.reply_text(
                "Minimum is 100 Stars. Enter a valid number:",
                reply_markup=cancel_keyboard()
            )
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
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=" ", 
            reply_markup=cancel_keyboard()
        )
        return ADD_STARS_STATE
    except ValueError:
        await update.message.reply_text(
            "Invalid input. Enter a number:",
            reply_markup=cancel_keyboard()
        )
        return ADD_STARS_STATE

async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    stars_amount = int(payment.total_amount)
    user_info = get_user_data(user_id)
    new_balance = user_info["balance"] + stars_amount
    new_total = user_info["total_deposits"] + stars_amount
    update_user_data(user_id, balance=new_balance, total_deposits=new_total)
    await update.message.reply_text(
        f"✅ Payment successful!\nAdded {stars_amount} Stars.\nNew balance: {new_balance} Stars",
        reply_markup=main_menu_keyboard_with_miniapp()
    )

async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Enter the amount of Stars you want to withdraw:",
        reply_markup=cancel_keyboard()
    )
    return WITHDRAW_AMOUNT_STATE

async def handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Cancel":
        await start(update, context)
        return ConversationHandler.END
    user_id = update.effective_user.id
    user_info = get_user_data(user_id)
    try:
        amount = int(update.message.text)
    except ValueError:
        await update.message.reply_text(
            "Invalid input. Enter a number:",
            reply_markup=cancel_keyboard()
        )
        return WITHDRAW_AMOUNT_STATE
    if amount <= 0:
        await update.message.reply_text(
            "Enter a number greater than 0:",
            reply_markup=cancel_keyboard()
        )
        return WITHDRAW_AMOUNT_STATE
    if amount > user_info["balance"]:
        await update.message.reply_text(
            "You don’t have enough balance. Try again:",
            reply_markup=cancel_keyboard()
        )
        return WITHDRAW_AMOUNT_STATE
    context.user_data["withdraw_amount"] = amount
    keyboard = [[InlineKeyboardButton("✅ Confirm Withdraw", callback_data="confirm_withdraw")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"You requested to withdraw {amount} Stars.\nClick confirm to proceed or ❌ Cancel.",
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
    vip_level = get_vip_level(user_info["total_deposits"])
    wallet_address = user_info["ton_wallet"] or "Not set"
    username = f"@{query.from_user.username}" if query.from_user.username else "No username"
    admin_message = (
        f"📤 New Withdrawal Request\n\n"
        f"👤 User ID: {user_id}\n"
        f"🔗 Username: {username}\n"
        f"⭐ Withdrawn: {amount} Stars\n"
        f"💳 Wallet: {wallet_address}\n"
        f"🏅 VIP Level: {vip_level}\n"
        f"💰 Remaining Balance: {new_balance} Stars"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_message)
    await query.edit_message_text(
        f"✅ Withdrawal request of {amount} Stars has been received.\n"
        f"Remaining balance: {new_balance} Stars.\n"
        f"Your TON will be sent soon."
    )
    await query.message.reply_text("Choose an option:", reply_markup=main_menu_keyboard_with_miniapp())

async def wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_info = get_user_data(update.effective_user.id)
    current_wallet = user_info["ton_wallet"] or "Not set"
    await update.message.reply_text(
        f"Your current TON wallet: `{current_wallet}`\nSend me your new TON wallet address:",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard()
    )
    return SET_WALLET_STATE

async def set_ton_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Cancel":
        await start(update, context)
        return ConversationHandler.END
    user_id = update.message.from_user.id
    new_wallet = update.message.text
    if not (new_wallet.startswith(("EQ", "UQ")) or new_wallet.endswith((".ton",))):
        await update.message.reply_text(
            "Invalid TON wallet address. Try again:",
            reply_markup=cancel_keyboard()
        )
        return SET_WALLET_STATE
    update_user_data(user_id, ton_wallet=new_wallet)
    await update.message.reply_text(
        f"✅ Your TON wallet has been updated successfully!\nCurrent wallet: `{new_wallet}`",
        parse_mode="Markdown"
    )
    await start(update, context)
    return ConversationHandler.END

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

# --- API Functions for Mini App ---
def validate_telegram_data(data):
    try:
        data_dict = dict(item.split('=', 1) for item in data.split('&'))
        hash_to_check = data_dict.pop('hash', None)
        if not hash_to_check:
            return False
        sorted_data = sorted([f"{key}={value}" for key, value in data_dict.items()])
        data_check_string = '\n'.join(sorted_data)
        secret_key = hmac.new(BOT_TOKEN.encode(), 'WebAppData'.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        return calculated_hash == hash_to_check
    except Exception as e:
        logging.error(f"Error validating data: {e}")
        return False

# --- API Endpoints ---
@app.route('/api/get_balance', methods=['POST'])
def get_balance():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    init_data = data.get('initData', '')
    if not validate_telegram_data(init_data):
        return jsonify({"error": "Invalid Data"}), 403
    try:
        user_id = json.loads(data.get('user', '{}')).get('id')
        if not user_id:
            return jsonify({"error": "User ID not found"}), 400
        user_info = get_user_data(user_id)
        return jsonify({
            "status": "success",
            "balance": user_info['balance'],
            "total_deposits": user_info['total_deposits'],
            "vip_level": get_vip_level(user_info['total_deposits'])
        })
    except Exception as e:
        logging.error(f"API Error in get_balance: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/api/request_withdraw', methods=['POST'])
def request_withdraw():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    init_data = data.get('initData', '')
    if not validate_telegram_data(init_data):
        return jsonify({"error": "Invalid Data"}), 403
    try:
        user_id = json.loads(data.get('user', '{}')).get('id')
        amount = int(data.get('amount'))
        if not user_id or not amount:
            return jsonify({"error": "Missing user ID or amount"}), 400
        user_info = get_user_data(user_id)
        if amount <= 0:
            return jsonify({"status": "fail", "message": "Withdrawal amount must be greater than zero."})
        if amount > user_info['balance']:
            return jsonify({"status": "fail", "message": "Insufficient balance."})
        new_balance = user_info['balance'] - amount
        update_user_data(user_id, balance=new_balance)
        wallet_address = user_info["ton_wallet"] or "Not set"
        admin_message = (
            f"📤 New Withdrawal Request from Mini App\n\n"
            f"👤 User ID: {user_id}\n"
            f"⭐ Withdrawn: {amount} Stars\n"
            f"💳 Wallet: {wallet_address}\n"
            f"💰 Remaining Balance: {new_balance} Stars"
        )
        asyncio.run(application.bot.send_message(chat_id=ADMIN_ID, text=admin_message))
        return jsonify({
            "status": "success",
            "message": f"Withdrawal request of {amount} Stars has been received.",
            "new_balance": new_balance
        })
    except Exception as e:
        logging.error(f"API Error in request_withdraw: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

# Function to serve the static mini app files
@app.route('/miniapp/<path:filename>')
def serve_miniapp(filename):
    return send_from_directory('mini_app', filename)

# The Telegram bot's webhook handler
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    update = Update.de_json(data, application.bot)
    asyncio.run(application.process_update(update))
    return 'ok'

# Global application variable
application = None

# Setup bot function
def setup_bot():
    global application
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(MessageHandler(filters.Regex("^👤 Account$"), account_handler))
    
    add_fund_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Add Funds$"), add_fund_start)],
        states={ADD_STARS_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_stars_amount)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), start), MessageHandler(filters.ALL, start)],
    )

    withdraw_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🏧 Withdraw$"), withdraw_handler)],
        states={WITHDRAW_AMOUNT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), start), MessageHandler(filters.ALL, start)],
    )

    wallet_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👛 Wallet$"), wallet_start)],
        states={SET_WALLET_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_ton_wallet)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), start), MessageHandler(filters.ALL, start)],
    )

    application.add_handler(add_fund_conv)
    application.add_handler(withdraw_conv)
    application.add_handler(wallet_conv)
    application.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    application.add_handler(CallbackQueryHandler(confirm_withdrawal, pattern="confirm_withdraw"))

# --- Run Setup ---
setup_bot()

# Flask run
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
