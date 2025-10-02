import logging
import os
import asyncio
from aiohttp import web
import asyncpg  # <-- تم التغيير هنا
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
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6172153716"))

# --- Global Database Pool ---
DB_POOL = None  # سيتم تهيئته في دالة main

# --- States ---
ADD_STARS_STATE, WITHDRAW_AMOUNT_STATE, SET_WALLET_STATE = range(3)

# --- Database functions (asyncpg version) ---
async def init_db():
    async with DB_POOL.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                balance BIGINT DEFAULT 0,
                ton_wallet TEXT,
                total_deposits BIGINT DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS start_users (
                user_id BIGINT PRIMARY KEY
            )
        """)

async def get_user_data(user_id: int) -> dict:
    async with DB_POOL.acquire() as conn:
        data = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        if not data:
            await conn.execute("INSERT INTO users (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING", user_id)
            # أعد الاستعلام للحصول على البيانات مع القيم الافتراضية
            data = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    
    # تحويل Record إلى dict لضمان التوافق
    return dict(data) if data else {"user_id": user_id, "balance": 0, "ton_wallet": None, "total_deposits": 0}

async def update_user_data(user_id: int, **kwargs):
    # بناء جملة التحديث ديناميكياً
    set_clauses = [f"{key} = ${i+2}" for i, key in enumerate(kwargs.keys())]
    query = f"UPDATE users SET {', '.join(set_clauses)} WHERE user_id = $1"
    
    async with DB_POOL.acquire() as conn:
        await conn.execute(query, user_id, *kwargs.values())

# --- VIP System ---
def get_vip_level(total_deposits):
    if total_deposits >= 150000: return "VIP 5"
    if total_deposits >= 100000: return "VIP 4"
    if total_deposits >= 50000:  return "VIP 3"
    if total_deposits >= 20000:  return "VIP 2"
    if total_deposits >= 10000:  return "VIP 1"
    return "VIP 0"

# --- Keyboards ---
def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🌟 Add Funds"), KeyboardButton("🏧 Withdraw")],
        [KeyboardButton("👤 Account"), KeyboardButton("💼 Wallet")]
    ], resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel")]], resize_keyboard=True)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await get_user_data(user_id) # استخدام await

    async with DB_POOL.acquire() as conn:
        await conn.execute("INSERT INTO start_users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)

    await update.message.reply_text(
        "Please choose an option from below:", 
        reply_markup=main_menu_keyboard()
    )

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with DB_POOL.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM start_users")
    await update.message.reply_text(f"📈 Number of unique users who pressed /start: {count}")

async def account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_info = await get_user_data(user.id) # استخدام await
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
            provider_token="", # PROVIDER_TOKEN should be set here
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
    user_info = await get_user_data(user_id) # استخدام await
    new_balance = user_info["balance"] + stars_amount
    new_total = user_info["total_deposits"] + stars_amount
    await update_user_data(user_id, balance=new_balance, total_deposits=new_total) # استخدام await
    await update.message.reply_text(
        f"✅ Payment successful!\nAdded {stars_amount} Stars.\nNew balance: {new_balance} Stars",
        reply_markup=main_menu_keyboard()
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
    user_info = await get_user_data(user_id) # استخدام await
    try:
        amount = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Invalid input. Enter a number:", reply_markup=cancel_keyboard())
        return WITHDRAW_AMOUNT_STATE

    if amount <= 0:
        await update.message.reply_text("Enter a number greater than 0:", reply_markup=cancel_keyboard())
        return WITHDRAW_AMOUNT_STATE

    if amount > user_info["balance"]:
        await update.message.reply_text("You don’t have enough balance. Try again:", reply_markup=cancel_keyboard())
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
    amount = context.user_data.get("withdraw_amount")
    if not amount:
        await query.edit_message_text("No withdrawal request found.")
        return

    user_info = await get_user_data(user_id) # استخدام await
    if amount > user_info["balance"]:
        await query.edit_message_text("Insufficient balance.")
        return
    
    new_balance = user_info["balance"] - amount
    await update_user_data(user_id, balance=new_balance) # استخدام await

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
    await query.message.reply_text("Choose an option:", reply_markup=main_menu_keyboard())

async def wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_info = await get_user_data(update.effective_user.id) # استخدام await
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
        await update.message.reply_text("Invalid TON wallet address. Try again:", reply_markup=cancel_keyboard())
        return SET_WALLET_STATE

    await update_user_data(user_id, ton_wallet=new_wallet) # استخدام await
    await update.message.reply_text(
        f"✅ Your TON wallet has been updated successfully!\nCurrent wallet: `{new_wallet}`",
        parse_mode="Markdown"
    )
    await start(update, context)
    return ConversationHandler.END

async def star_transaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This handler is designed for native Telegram Stars payments, not invoice payments.
    # It might need adjustment based on the final implementation of Stars API.
    if getattr(update, "star_transaction", None):
        star_transaction = update.star_transaction
        user_id = star_transaction.payer.id
        amount = star_transaction.amount
        
        # A simple logic to add stars upon receiving a payment.
        user_info = await get_user_data(user_id) # استخدام await
        new_balance = user_info["balance"] + amount
        new_total = user_info["total_deposits"] + amount
        await update_user_data(user_id, balance=new_balance, total_deposits=new_total) # استخدام await
        await context.bot.send_message(
            chat_id=user_id,
            text=f"✅ Payment received: {amount} Stars\nYour new balance: {new_balance} Stars"
        )

# --- Main (Modified part) ---
async def main():
    global DB_POOL
    # إنشاء pool الاتصالات عند بدء التشغيل
    try:
        DB_POOL = await asyncpg.create_pool(DATABASE_URL)
        logging.info("Database connection pool established.")
    except Exception as e:
        logging.error(f"Failed to connect to the database: {e}")
        return

    await init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()

    # Add all your handlers
    add_fund_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🌟 Add Funds$"), add_fund_start)],
        states={ADD_STARS_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_stars_amount)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), start)],
    )
    withdraw_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🏧 Withdraw$"), withdraw_handler)],
        states={WITHDRAW_AMOUNT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), start)],
    )
    wallet_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💼 Wallet$"), wallet_start)],
        states={SET_WALLET_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_ton_wallet)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), start)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(MessageHandler(filters.Regex("^👤 Account$"), account_handler))
    application.add_handler(add_fund_conv)
    application.add_handler(withdraw_conv)
    application.add_handler(wallet_conv)
    application.add_handler(CallbackQueryHandler(confirm_withdrawal, pattern="^confirm_withdraw$"))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    application.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    application.add_handler(MessageHandler(filters.ALL, star_transaction_handler))
    
    # --- Web server setup ---
    PORT = int(os.environ.get("PORT", 8080))
    URL = os.environ.get("RENDER_EXTERNAL_URL")
    
    await application.initialize()
    if URL:
        await application.bot.set_webhook(url=f"{URL}/{BOT_TOKEN}")
    else:
        logging.warning("RENDER_EXTERNAL_URL is not set. Webhook will not be set.")

    async def telegram_webhook(request: web.Request) -> web.Response:
        try:
            data = await request.json()
            update = Update.de_json(data, application.bot)
            await application.process_update(update)
            return web.Response(text="OK", status=200)
        except Exception as e:
            logging.error(f"Error processing update: {e}")
            return web.Response(text="Internal Server Error", status=500)

    async def health_check(request: web.Request) -> web.Response:
        return web.Response(text="OK - I am alive!", status=200)
    
    webapp = web.Application()
    webapp.router.add_post(f"/{BOT_TOKEN}", telegram_webhook)
    webapp.router.add_get("/", health_check)
    
    runner = web.AppRunner(webapp)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=PORT)
    await site.start()
    logging.info(f"Server started on port {PORT}")
    
    await asyncio.Event().wait()
    
    # Clean up on shutdown
    await runner.cleanup()
    await DB_POOL.close() # <-- إغلاق pool الاتصالات
    await application.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
