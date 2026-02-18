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

DB_POOL = None 
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

def get_vip_level(total_deposits):
    if total_deposits >= 150000: return "VIP 5"
    if total_deposits >= 100000: return "VIP 4"
    if total_deposits >= 50000:  return "VIP 3"
    if total_deposits >= 20000:  return "VIP 2"
    if total_deposits >= 10000:  return "VIP 1"
    return "VIP 0"

def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🌟 Add Funds"), KeyboardButton("🏧 Withdraw")],
        [KeyboardButton("👤 Account"), KeyboardButton("💼 Wallet")]
    ], resize_keyboard=True)

def cancel_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ Cancel")]], resize_keyboard=True)

# --- المهمة الخلفية للإرسال (تمنع التكرار) ---
async def run_broadcast_task(bot, admin_id):
    async with DB_POOL.acquire() as conn:
        users = await conn.fetch("SELECT user_id FROM start_users")
    
    text = (
        "🚀 **ابدأ رحلة الأرباح اليوم!**\n"
        "هل أنت مستعد لتحويل وقتك إلى مكاسب حقيقية؟ لقد أطلقنا ميزاتنا الجديدة التي تتيح لك الكسب بسهولة وسرعة من خلال بوتنا.\n\n"
        "🚀 **Start Your Earning Journey Today!**\n"
        "Ready to turn your time into real profits?\n\n"
        "👇 اضغط أدناه للبدء | Click below to start:"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 ابدأ الكسب | Start Earning 💰", url="https://t.me/AiCryptoGPTbot?start=earn")]
    ])

    success, blocked = 0, 0
    for record in users:
        try:
            await bot.send_message(chat_id=record['user_id'], text=text, reply_markup=keyboard, parse_mode="Markdown")
            success += 1
            await asyncio.sleep(0.05)
            if success % 30 == 0: await asyncio.sleep(1)
        except:
            blocked += 1
            continue
    
    await bot.send_message(chat_id=admin_id, text=f"✅ اكتمل الإرسال!\n🟢 نجاح: {success}\n🔴 حظر: {blocked}")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("🚀 بدأت العملية في الخلفية، سأخبرك عند الانتهاء.")
    # تشغيل الإرسال كـ Task منفصل لكي لا يتهنج البوت ويرسل التحديث مراراً
    asyncio.create_task(run_broadcast_task(context.bot, ADMIN_ID))

# --- باقي الـ Handlers كما هي ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await get_user_data(user_id)
    async with DB_POOL.acquire() as conn:
        await conn.execute("INSERT INTO start_users (user_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)
    await update.message.reply_text("Please choose an option:", reply_markup=main_menu_keyboard())

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with DB_POOL.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM start_users")
    await update.message.reply_text(f"📈 Users: {count}")

async def account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_info = await get_user_data(update.effective_user.id)
    vip = get_vip_level(user_info.get("total_deposits", 0))
    msg = (f"👤 Account: {update.effective_user.id}\n- Balance: {user_info['balance']} Stars\n- VIP: {vip}")
    await update.message.reply_text(msg)

async def add_fund_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Min 100 Stars:", reply_markup=cancel_keyboard())
    return ADD_STARS_STATE

async def get_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel":
        await start(update, context); return ConversationHandler.END
    try:
        amt = int(update.message.text)
        if amt < 100: raise ValueError
        await context.bot.send_invoice(chat_id=update.effective_chat.id, title="Buy Stars", description=f"{amt} Stars", payload=str(amt), provider_token="", currency="XTR", prices=[LabeledPrice("Stars", amt)])
        return ADD_STARS_STATE
    except:
        await update.message.reply_text("Invalid."); return ADD_STARS_STATE

async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p = update.message.successful_payment
    u = await get_user_data(update.effective_user.id)
    await update_user_data(update.effective_user.id, balance=u["balance"]+p.total_amount, total_deposits=u["total_deposits"]+p.total_amount)
    await update.message.reply_text("✅ Success", reply_markup=main_menu_keyboard())

async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Amount to withdraw:", reply_markup=cancel_keyboard())
    return WITHDRAW_AMOUNT_STATE

async def handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel":
        await start(update, context); return ConversationHandler.END
    try:
        amt = int(update.message.text)
        u = await get_user_data(update.effective_user.id)
        if amt <= 0 or amt > u["balance"]: raise ValueError
        context.user_data["withdraw_amount"] = amt
        await update.message.reply_text(f"Confirm {amt}?", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Confirm", callback_data="confirm_withdraw")]]))
        return ConversationHandler.END
    except:
        await update.message.reply_text("Invalid."); return WITHDRAW_AMOUNT_STATE

async def confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    amt = context.user_data.get("withdraw_amount")
    u = await get_user_data(query.from_user.id)
    if amt and amt <= u["balance"]:
        await update_user_data(query.from_user.id, balance=u["balance"]-amt)
        await context.bot.send_message(ADMIN_ID, f"Withdraw: {query.from_user.id} - {amt}")
        await query.edit_message_text(f"✅ Received. Remaining: {u['balance']-amt}")

async def wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = await get_user_data(update.effective_user.id)
    await update.message.reply_text(f"Wallet: `{u['ton_wallet']}`\nNew address:", parse_mode="Markdown", reply_markup=cancel_keyboard())
    return SET_WALLET_STATE

async def set_ton_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ Cancel":
        await start(update, context); return ConversationHandler.END
    await update_user_data(update.effective_user.id, ton_wallet=update.message.text)
    await update.message.reply_text("✅ Updated")
    await start(update, context); return ConversationHandler.END

async def main():
    global DB_POOL
    try:
        DB_POOL = await asyncpg.create_pool(DATABASE_URL)
        await init_db()
    except Exception as e:
        logging.error(f"DB Error: {e}"); return

    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status_handler))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(MessageHandler(filters.Regex("^👤 Account$"), account_handler))
    application.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex("^🌟 Add Funds$"), add_fund_start)], states={ADD_STARS_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_stars_amount)]}, fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), start)]))
    application.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex("^🏧 Withdraw$"), withdraw_handler)], states={WITHDRAW_AMOUNT_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)]}, fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), start)]))
    application.add_handler(ConversationHandler(entry_points=[MessageHandler(filters.Regex("^💼 Wallet$"), wallet_start)], states={SET_WALLET_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_ton_wallet)]}, fallbacks=[MessageHandler(filters.Regex("^❌ Cancel$"), start)]))
    application.add_handler(CallbackQueryHandler(confirm_withdrawal, pattern="^confirm_withdraw$"))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))
    application.add_handler(PreCheckoutQueryHandler(precheckout_handler))

    PORT = int(os.environ.get("PORT", 8080))
    URL = os.environ.get("RENDER_EXTERNAL_URL")
    await application.initialize()
    if URL: await application.bot.set_webhook(url=f"{URL}/{BOT_TOKEN}")

    async def telegram_webhook(request):
        data = await request.json()
        await application.process_update(Update.de_json(data, application.bot))
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
