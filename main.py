import logging
import os
import re
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# إعداد السجل (Logging) للمساعدة في تتبع الأخطاء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ضع توكن البوت الخاص بك هنا (يفضل استخدامه كمتغير بيئة)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# حالات المحادثة
ADD_STARS_STATE, WITHDRAW_STARS_STATE, SET_WALLET_STATE = range(3)

# قاموس لتخزين بيانات المستخدمين (للتجربة فقط، يفضل استخدام قاعدة بيانات)
user_data = {}

def get_user_info(user_id):
    """دالة لجلب بيانات المستخدم، تقوم بإنشاء حساب جديد إذا لم يكن موجوداً."""
    if user_id not in user_data:
        user_data[user_id] = {
            'balance': 0,
            'ton_wallet': None
        }
    return user_data[user_id]

# Handlers للأوامر الأساسية

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الرد على أمر /start وإظهار قائمة الأزرار."""
    user_id = update.effective_user.id
    get_user_info(user_id) # تأكد من أن المستخدم لديه بيانات
    
    menu_keyboard = [
        [KeyboardButton("➕ Add Fund"), KeyboardButton("🏧 Withdraw")],
        [KeyboardButton("👤 Account"), KeyboardButton("👛 Wallet")]
    ]
    reply_markup = ReplyKeyboardMarkup(menu_keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Welcome! Choose an option:",
        reply_markup=reply_markup
    )

async def account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """عرض تفاصيل الحساب."""
    user = update.effective_user
    user_info = get_user_info(user.id)
    
    wallet_address = user_info['ton_wallet'] if user_info['ton_wallet'] else "Not set"
    
    response_text = (
        f"Your Account:\n"
        f"- ID: {user.id}\n"
        f"- Username: @{user.username}\n"
        f"- Your Balance: {user_info['balance']} Stars\n"
        f"- Your TON Wallet: {wallet_address}"
    )
    
    await update.message.reply_text(response_text)

# Handlers لعملية Add Fund

async def add_fund_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يبدأ عملية إضافة النجوم ويطلب المبلغ."""
    await update.message.reply_text("How many Stars do you want to add? (min: 100,):")
    return ADD_STARS_STATE

async def get_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يتلقى المبلغ ويتحقق منه."""
    try:
        stars_amount = int(update.message.text)
        if stars_amount < 100:
            await update.message.reply_text("The minimum amount is 100 stars. Please enter a valid number:")
            return ADD_STARS_STATE
            
        # إنشاء زر الدفع الديناميكي
        pay_url = f"https://t.me/stars?startApp=stars_bot&amount={stars_amount}"
        keyboard = [[InlineKeyboardButton(f"Pay {stars_amount} Stars", url=pay_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Please click the button to pay {stars_amount} Stars:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("Invalid input. Please enter a number:")
        return ADD_STARS_STATE

# Handlers لعملية Withdraw

async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض رصيد المستخدم ويسأل عن السحب."""
    user_id = update.effective_user.id
    user_info = get_user_info(user_id)
    
    if user_info['balance'] == 0:
        await update.message.reply_text("Your balance is 0 stars.")
        return ConversationHandler.END
    
    response_text = (
        f"Your current balance is: {user_info['balance']} Stars.\n"
        f"The stars you withdraw will be sent to your TON wallet as TON coin within 24 hours.\n"
        f"Are you sure you want to proceed?"
    )
    
    keyboard = [[InlineKeyboardButton("Confirm Withdrawal", callback_data="confirm_withdraw")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(response_text, reply_markup=reply_markup)
    return WITHDRAW_STARS_STATE

async def confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يتعامل مع تأكيد السحب."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_info = get_user_info(user_id)
    
    # هنا يتم استدعاء دالة تحويل النجوم إلى TON
    # await send_ton(user_info['ton_wallet'], user_info['balance'])
    
    await query.edit_message_text("Your withdrawal request has been submitted successfully. The TON will be sent to your wallet shortly.")
    
    # قم بتصفير الرصيد بعد السحب
    user_info['balance'] = 0 
    
    return ConversationHandler.END

# Handlers لعملية Wallet

async def wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض المحفظة الحالية ويطلب عنوان جديد."""
    user_id = update.effective_user.id
    user_info = get_user_info(user_id)
    
    current_wallet = user_info['ton_wallet'] if user_info['ton_wallet'] else "Not set"
    await update.message.reply_text(f"Your current TON wallet is: `{current_wallet}`\nPlease send me your new TON wallet address to save it:", parse_mode='Markdown')
    return SET_WALLET_STATE

async def set_ton_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يتلقى عنوان المحفظة ويحفظه."""
    user_id = update.effective_user.id
    new_wallet = update.message.text
    
    # تحقق بسيط من شكل العنوان (يمكن تحسينه)
    if not new_wallet.startswith(("EQ", "UQ")):
        await update.message.reply_text("Invalid TON wallet address. Please send a valid one.")
        return SET_WALLET_STATE
        
    user_data[user_id]['ton_wallet'] = new_wallet
    await update.message.reply_text(f"Your new TON wallet has been saved: `{new_wallet}`", parse_mode='Markdown')
    return ConversationHandler.END

def main() -> None:
    """تشغيل البوت."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation Handlers
    add_fund_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Add Fund$"), add_fund_start)],
        states={
            ADD_STARS_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_stars_amount)],
        },
        fallbacks=[CommandHandler("cancel", start)],
    )

    wallet_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👛 Wallet$"), wallet_start)],
        states={
            SET_WALLET_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_ton_wallet)],
        },
        fallbacks=[CommandHandler("cancel", start)],
    )
    
    # إضافة Handlers للأوامر والأزرار
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^👤 Account$"), account_handler))
    application.add_handler(add_fund_conv_handler)
    application.add_handler(wallet_conv_handler)
    
    # Withdraw Handler
    application.add_handler(MessageHandler(filters.Regex("^🏧 Withdraw$"), withdraw_handler))
    application.add_handler(CallbackQueryHandler(confirm_withdrawal, pattern="^confirm_withdraw$"))
    
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
