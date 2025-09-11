import logging
import os
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# إعداد السجل (Logging) للمساعدة في تتبع الأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ضع توكن البوت الخاص بك هنا
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
# إذا كنت تعمل محليًا، يمكنك استخدام التوكن مباشرة
# BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# قائمة الأوامر التي ستظهر في القائمة
async def set_bot_commands(application: Application):
    commands = [
        BotCommand("addfund", "إضافة نجوم"),
        BotCommand("withdraw", "سحب عملة TON"),
        BotCommand("account", "عرض الرصيد"),
        BotCommand("wallet", "إضافة/تغيير محفظة TON"),
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إرسال رسالة ترحيب وعرض الأزرار."""
    # إنشاء أزرار القائمة (Menu Buttons)
    menu_keyboard = [
        [KeyboardButton("➕ Add Fund"), KeyboardButton("🏧 Withdraw")],
        [KeyboardButton("👤 Account"), KeyboardButton("👛 Wallet")]
    ]
    reply_markup = ReplyKeyboardMarkup(menu_keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=reply_markup
    )

async def add_fund_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الرد على زر 'Add Fund'."""
    # إنشاء زر مدمج للدفع
    keyboard = [[InlineKeyboardButton("Pay 71 Stars", url="https://t.me/tg_stars_bot?start=pay_71")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "اضغط على الزر أدناه لإضافة 71 نجمة:",
        reply_markup=reply_markup
    )

async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الرد على زر 'Withdraw'."""
    await update.message.reply_text("أرسل لي عدد النجوم التي تريد سحبها وعنوان محفظة TON الخاصة بك.")

async def account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الرد على زر 'Account'."""
    user_stars_balance = 171 # مثال على رصيد
    await update.message.reply_text(f"Your Balance: {user_stars_balance} Stars.")

async def wallet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الرد على زر 'Wallet'."""
    await update.message.reply_text("أرسل لي عنوان محفظة TON الخاصة بك لحفظه أو تحديثه.")

def main() -> None:
    """تشغيل البوت."""
    application = Application.builder().token(BOT_TOKEN).build()

    # إضافة Handlers للأوامر والأزرار
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^➕ Add Fund$"), add_fund_handler))
    application.add_handler(MessageHandler(filters.Regex("^🏧 Withdraw$"), withdraw_handler))
    application.add_handler(MessageHandler(filters.Regex("^👤 Account$"), account_handler))
    application.add_handler(MessageHandler(filters.Regex("^👛 Wallet$"), wallet_handler))

    # تعيين قائمة الأوامر عند تشغيل البوت لأول مرة
    # يمكنك إزالة هذه الأسطر إذا قمت بتعيين الأوامر يدوياً عبر BotFather
    # application.run_polling(allowed_updates=Update.ALL_TYPES)
    # ملاحظة: يجب أن تقوم بتشغيل set_bot_commands() مرة واحدة فقط لتظهر الأوامر في القائمة
    # await set_bot_commands(application)

    # تشغيل البوت باستخدام Webhooks
    PORT = int(os.environ.get('PORT', 8080))
    URL = os.environ.get("RENDER_EXTERNAL_URL", "https://your-render-app-name.onrender.com")

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{URL}/{BOT_TOKEN}"
    )
    logging.info(f"Webhook started at {URL}:{PORT}")


if __name__ == '__main__':
    main()
