import logging
import os
import asyncio
import random
from aiohttp import web
import asyncpg
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
DB_POOL = None 

# --- States ---
ADD_STARS_STATE, WITHDRAW_AMOUNT_STATE, SET_WALLET_STATE = range(3)

# --- Database functions ---
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
            data = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
    return dict(data) if data else {"user_id": user_id, "balance": 0, "ton_wallet": None, "total_deposits": 0}

async def update_user_data(user_id: int, **kwargs):
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

# --- Broadcast Logic (The New Part) ---
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إرسال إعلان لجميع المستخدمين بشكل آمن"""
    if update.effective_user.id != ADMIN_ID:
        return

    # جلب جميع المستخدمين من قاعدة البيانات
    async with DB_POOL.acquire() as conn:
        users = await conn.fetch("SELECT user_id FROM start_users")
    
    total_users = len(users)
    await update.message.reply_text(f"🚀 جاري بدء الإرسال لـ {total_users} مستخدم...")

    # نص الإعلان والزر
    text = (
        "🚀 **ابدأ رحلة الأرباح اليوم!**\n"
        "هل أنت مستعد لتحويل وقتك إلى مكاسب حقيقية؟ لقد أطلقنا ميزاتنا الجديدة التي تتيح لك الكسب بسهولة وسرعة من خلال بوتنا.\n\n"
        "🚀 **Start Your Earning Journey Today!**\n"
        "Ready to turn your time into real profits? We've launched new features that let you earn easily and fast.\n\n"
        "👇 اضغط أدناه للبدء | Click below to start:"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 ابدأ الكسب | Start Earning 💰", url="https://t.me/AiCryptoGPTbot?start=earn")]
    ])

    success = 0
    blocked = 0

    for record in users:
        uid = record['user_id']
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            success += 1
            # تأخير بسيط جداً لمنع الـ Flood
            await asyncio.sleep(0.05) 
            
            # استراحة كل 30 رسالة
            if success % 30 == 0:
                await asyncio.sleep(1)

        except Exception as e:
            blocked += 1
            continue

    await update.message.reply_text(
        f"✅ اكتمل الإرسال!\n\n"
        f"🟢 نجاح: {success}\n"
        f"🔴 فشل (حظر): {blocked}"
    )

# --- Existing Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await get_user_data(user_id)
    async with DB_POOL.acquire() as conn:
        await conn.execute("INSERT INTO start_users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)
    await update.message.reply_text("Please choose an option from below:", reply_markup=main_menu_keyboard())

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with DB_POOL.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM start_users")
    await update.message.reply_text(f"📈 Number of unique users: {count}")

async def account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_info = await get_user_data(user.id)
    wallet_address = user_info["ton_wallet"] or "Not set"
    total_deposits = user_info.get("total_deposits", 0)
    vip_level = get_vip_level(total_deposits)
    response_text = (
        f"👤 Your Account:\n- ID: {user.id}\n- Username: @{user.username}\n"
        f"- Balance: {user_info['balance']} Stars\n- TON Wallet: {wallet_address}\n"
        f"- VIP Level: {vip_level}\n- Total Deposits: {total_deposits} Stars"
    )
    await update.message.reply_text(response_text)

async def add_fund_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Enter the number of Stars you want to add (min: 100):", reply_markup=cancel_keyboard())
    return ADD_STARS_STATE

async def get_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Cancel":
        await start(update, context); return ConversationHandler.END
    try:
        stars_amount = int(update.message.text)
        if stars_amount < 100:
            await update.message.reply_text("Minimum is 100 Stars.", reply_markup=cancel_keyboard())
            return ADD_STARS_STATE
        prices = [LabeledPrice("Stars", stars_amount)]
        await context.bot.send_invoice(
            chat_id=update.effective_chat.id, title="Buy Stars",
            description=f"Adding {stars_amount} Stars", payload=str(stars_amount),
            provider_token="", currency="XTR", prices=prices
        )
        return ADD_STARS_STATE
    except ValueError:
        await update.message.reply_text("Invalid input.", reply_markup=cancel_keyboard())
        return ADD_STARS_STATE

async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    stars_amount = int(payment.total_amount)
    user_info = await get_user_data(user_id)
    new_balance = user_info["balance"] + stars_amount
    new_total = user_info["total_deposits"] + stars_amount
    await update_user_data(user_id, balance=new_balance, total_deposits=new_total)
    await update.message.reply_text(f"✅ Added {stars_amount} Stars.", reply_markup=main_menu_keyboard())

async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Enter the amount of Stars to withdraw:", reply_markup=cancel_keyboard())
    return WITHDRAW_AMOUNT_STATE

async def handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Cancel":
        await start(update, context); return ConversationHandler.END
    user_id = update.effective_user.id
    user_info = await get_user_data(user_id)
    try:
        amount = int(update.message.text)
        if amount <= 0 or amount > user_info["balance"]:
            raise ValueError
        context.user_data["withdraw_amount"] = amount
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Confirm", callback_data="confirm_withdraw")]])
        await update.message.reply_text(f"Withdraw {amount} Stars?", reply_markup=reply_markup)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Invalid amount.", reply_markup=cancel_keyboard())
        return WITHDRAW_AMOUNT_STATE

async def confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    amount = context.user_data.get("withdraw_amount")
    user_info = await get_user_data(user_id)
    if amount and amount <= user_info["balance"]:
        new_balance = user_info["balance"] - amount
        await update_user_data(user_id, balance=new_balance)
        admin_msg = f"📤 Withdrawal: {user_id} - {amount} Stars\nWallet: {user_info['ton_wallet']}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg)
        await query.edit_message_text(f"✅ Request received. Remaining: {new_balance}")
        await query.message.reply_text("Menu:", reply_markup=main_menu_keyboard())

async def wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_info = await get_user_data(update.effective_user.id)
    await update.message.reply_text(f"Current: `{user_info['ton_wallet']}`\nSend new address:", parse_mode="Markdown", reply_markup=cancel_keyboard())
    return SET_WALLET_STATE

async def set_ton_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "❌ Cancel":
        await start(update, context); return ConversationHandler.END
    new_wallet = update.message.text
    if not (new_wallet.startswith(("EQ", "UQ")) or ".ton" in new_wallet):
        await update.message.reply_text("Invalid address.", reply_markup=cancel_keyboard())
        return SET_WALLET_STATE
    await update_user_data(update.effective_user.id, ton_wallet=new_wallet)
    await update.message.reply_text("✅ Wallet updated.")
    await start(update, context)
    return ConversationHandler.END

async def star_transaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if getattr(update, "star_transaction", None):
        st = update.star_transaction
        user_info = await get_user_data(st.payer.id)
        nb = user_info["balance"] + st.amount
        await update_user_data(st.payer.id, balance=nb, total_deposits=user_info["total_deposits"]+st.amount)

# --- Main ---
async def main():
    global DB_POOL
    try:
        DB_POOL = await asyncpg.create_pool(DATABASE_URL)
        logging.info("DB Connected.")
    except Exception as e:
        logging.error(f"DB Error: {e}"); return

    await init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("broadcast", broadcast_command)) # الأمر الجديد للآدمن
    application.add_handler(MessageHandler(filters.Regex("^👤 Account$"), account_handler))
    
    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🌟 Add Funds$"), add_fund_start)],
        states={ADD_STARS_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_stars_amount)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), start)],
    ))
    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🏧 Withdraw$"), withdraw_handler)],
        states={WITHDRAW_AMOUNT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), start)],
    ))
    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💼 Wallet$"), wallet_start)],
        states={SET_WALLET_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_ton_wallet)]},
        fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), start)],
    ))

    application.add_handler(CallbackQueryHandler(confirm_withdrawal, pattern="^confirm_withdraw$"))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    application.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    application.add_handler(MessageHandler(filters.ALL, star_transaction_handler))
    
    PORT = int(os.environ.get("PORT", 8080))
    URL = os.environ.get("RENDER_EXTERNAL_URL")
    
    await application.initialize()
    if URL:
        await application.bot.set_webhook(url=f"{URL}/{BOT_TOKEN}")
    
    async def telegram_webhook(request):
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response(text="OK")

    webapp = web.Application()
    webapp.router.add_post(f"/{BOT_TOKEN}", telegram_webhook)
    webapp.router.add_get("/", lambda r: web.Response(text="Alive"))
    
    runner = web.AppRunner(webapp)
    await runner.setup()
    await web.TCPSite(runner, host="0.0.0.0", port=PORT).start()
    
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
