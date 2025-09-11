import logging
import os
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# إعداد السجل (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# الحصول على توكن البوت من متغيرات البيئة
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# يمكنك وضع متغيرات أخرى هنا (مثل معلومات محفظة TON)
TON_WALLET_ADDRESS = os.environ.get("TON_WALLET_ADDRESS")
TON_WALLET_SEED_PHRASE = os.environ.get("TON_WALLET_SEED_PHRASE")

# هنا يجب أن تقوم بتهيئة محفظة TON الخاصة بك
# import tonpy
# keystore = tonpy.KeyStore(TON_WALLET_SEED_PHRASE, "", "")
# ...

async def set_bot_commands(application: Application):
    """إعداد الأوامر التي تظهر في قائمة البوت."""
    commands = [
        BotCommand("start", "بدء البوت"),
        BotCommand("addfund", "إضافة نجوم"),
        BotCommand("withdraw", "سحب TON"),
        BotCommand("account", "عرض الرصيد"),
        BotCommand("wallet", "تغيير محفظة TON"),
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الرد على أمر /start وإظهار قائمة الأزرار."""
    menu_keyboard = [
        [KeyboardButton("➕ Add Fund"), KeyboardButton("🏧 Withdraw")],
        [KeyboardButton("👤 Account"), KeyboardButton("👛 Wallet")]
    ]
    reply_markup = ReplyKeyboardMarkup(menu_keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=reply_markup
    )

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """التعامل مع ضغطات أزرار القائمة الرئيسية."""
    user_choice = update.message.text
    if user_choice == "➕ Add Fund":
        await add_fund_handler(update, context)
    elif user_choice == "🏧 Withdraw":
        await withdraw_handler(update, context)
    elif user_choice == "👤 Account":
        await account_handler(update, context)
    elif user_choice == "👛 Wallet":
        await wallet_handler(update, context)

async def add_fund_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """إرسال رسالة بإظهار زر 'Pay'."""
    # هنا يمكنك جعل عدد النجوم ديناميكياً
    stars_to_pay = 71
    # رابط الدفع يجب أن يكون خاصاً ببوتك
    pay_url = f"https://t.me/your_bot_username?start=pay_{stars_to_pay}"
    keyboard = [[InlineKeyboardButton(f"Pay {stars_to_pay} Stars", url=pay_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "اضغط على الزر أدناه لإضافة نجوم:",
        reply_markup=reply_markup
    )

async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """التعامل مع طلب السحب."""
    await update.message.reply_text("أرسل لي عدد النجوم التي تريد سحبها وعنوان محفظة TON الخاصة بك.")

async def account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض رصيد المستخدم."""
    user_stars_balance = 171
    await update.message.reply_text(f"Your Balance: {user_stars_balance} Stars.")

async def wallet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """التعامل مع تغيير عنوان المحفظة."""
    await update.message.reply_text("أرسل لي عنوان محفظة TON الخاصة بك لحفظه أو تحديثه.")

def main() -> None:
    """وظيفة تشغيل البوت."""
    application = Application.builder().token(BOT_TOKEN).build()

    # إضافة Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    application.add_handler(CommandHandler("addfund", add_fund_handler))
    application.add_handler(CommandHandler("withdraw", withdraw_handler))
    application.add_handler(CommandHandler("account", account_handler))
    application.add_handler(CommandHandler("wallet", wallet_handler))
    
    # يجب أن يتم تعيين الأوامر مرة واحدة فقط
    # application.bot.set_my_commands([BotCommand("start", "...")])

    # تشغيل البوت
    # إذا كنت تستخدم Render، فإنك تحتاج إلى تشغيله بـ Webhooks
    # وإذا كنت تستخدمه محلياً، يمكنك استخدام Polling
    
    if os.environ.get("RENDER_URL"):
        # إعداد Webhooks للتشغيل على Render
        PORT = int(os.environ.get('PORT', 8080))
        WEBHOOK_URL = os.environ.get("RENDER_URL")
        application.run_webhook(listen="0.0.0.0",
                                port=PORT,
                                url_path=BOT_TOKEN,
                                webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}")
        logging.info("Webhook started successfully.")
    else:
        # تشغيل محلي باستخدام Polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        logging.info("Polling started successfully.")

if __name__ == '__main__':
    # هنا يمكنك إعداد الأوامر لمرة واحدة
    # import asyncio
    # async def setup():
    #     application = Application.builder().token(BOT_TOKEN).build()
    #     await set_bot_commands(application)
    # asyncio.run(setup())
    
    main()
