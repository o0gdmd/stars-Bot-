import logging
import os
import sqlite3
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
ADD_STARS_STATE, SET_WALLET_STATE = range(2)

# --- الدوال الخاصة بقاعدة البيانات (SQLite) ---
def init_db():
    """تهيئة قاعدة البيانات وإنشاء جدول المستخدمين."""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            ton_wallet TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_user_data(user_id):
    """جلب بيانات المستخدم من قاعدة البيانات أو إنشاء حساب جديد."""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    data = cursor.fetchone()
    if not data:
        cursor.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        data = (user_id, 0, None)
    conn.close()
    return {'user_id': data[0], 'balance': data[1], 'ton_wallet': data[2]}

def update_user_data(user_id, **kwargs):
    """تحديث بيانات المستخدم في قاعدة البيانات."""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    for key, value in kwargs.items():
        cursor.execute(f'UPDATE users SET {key} = ? WHERE user_id = ?', (value, user_id))
    conn.commit()
    conn.close()

# --- Handlers للأوامر الأساسية ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الرد على أمر /start وإظهار قائمة الأزرار."""
    user_id = update.effective_user.id
    get_user_data(user_id)
    
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
    user_info = get_user_data(user.id)
    
    wallet_address = user_info['ton_wallet'] if user_info['ton_wallet'] else "Not set"
    response_text = (
        f"Your Account:\n"
        f"- ID: {user.id}\n"
        f"- Username: @{user.username}\n"
        f"- Your Balance: {user_info['balance']} Stars\n"
        f"- Your TON Wallet: {wallet_address}"
    )
    await update.message.reply_text(response_text)

# --- Handlers لعملية Add Fund ---

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
            
        # === هذا هو الكود الذي يجب استخدامه لضمان الرابط الصحيح ===
        bot_username = context.bot.username
        pay_url = f"https://t.me/stars?startApp={bot_username}&amount={stars_amount}"
        # ==========================================================
        
        keyboard = [[InlineKeyboardButton(f"Pay {stars_amount} Stars", url=pay_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Please click the button to pay {stars_amount} Stars directly to the bot:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("Invalid input. Please enter a number:")
        return ADD_STARS_STATE

# --- Handlers لعملية Withdraw ---

async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يتحقق من الرصيد ويعرض خيار السحب."""
    user_info = get_user_data(update.effective_user.id)
    
    if user_info['balance'] < 100:
        await update.message.reply_text("Your balance must be at least 100 Stars to withdraw.")
        return
    
    response_text = (
        f"Your current balance is: {user_info['balance']} Stars.\n"
        f"Do you want to confirm the withdrawal?"
    )
    
    keyboard = [[InlineKeyboardButton("Confirm Withdrawal", callback_data="confirm_withdraw")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(response_text, reply_markup=reply_markup)
    return

async def confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يتعامل مع تأكيد السحب."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_info = get_user_data(user_id)

    if user_info['ton_wallet'] is None:
        await query.edit_message_text("Error: Please set your TON Wallet address first using the 'Wallet' button.")
        return
        
    # هنا يتم استدعاء دالة تحويل النجوم إلى TON
    # await send_ton(user_info['ton_wallet'], user_info['balance'])
    
    await query.edit_message_text("Your withdrawal request has been submitted successfully. The TON will be sent to your wallet shortly.")
    
    update_user_data(user_id, balance=0)

# --- Handlers لعملية Wallet ---

async def wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يعرض المحفظة الحالية ويطلب عنوان جديد."""
    user_info = get_user_data(update.effective_user.id)
    
    current_wallet = user_info['ton_wallet'] if user_info['ton_wallet'] else "Not set"
    await update.message.reply_text(f"Your current TON wallet is: `{current_wallet}`\nPlease send me your new TON wallet address to save it:", parse_mode='Markdown')
    return SET_WALLET_STATE

async def set_ton_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """يتلقى عنوان المحفظة ويحفظه."""
    user_id = update.effective_user.id
    new_wallet = update.message.text
    
    if not (new_wallet.startswith(("EQ", "UQ")) or new_wallet.endswith((".ton",))):
        await update.message.reply_text("Invalid TON wallet address. Please send a valid one.")
        return SET_WALLET_STATE
        
    update_user_data(user_id, ton_wallet=new_wallet)
    await update.message.reply_text(f"Your new TON wallet has been saved: `{new_wallet}`", parse_mode='Markdown')
    return ConversationHandler.END

# --- Handler لاستقبال النجوم ---
async def star_transaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة المعاملات الواردة من النجوم."""
    if update.star_transaction:
        star_transaction = update.star_transaction
        user_id = star_transaction.payer.id
        amount = star_transaction.amount

        if star_transaction.type == 'StarsPayment':
            user_info = get_user_data(user_id)
            current_balance = user_info['balance']
            new_balance = current_balance + amount
            
            update_user_data(user_id, balance=new_balance)
            
            await context.bot.send_message(
                chat_id=user_id,
                text=f"تم استلام دفعة {amount} نجمة بنجاح!\nرصيدك الحالي هو: {new_balance} نجمة."
            )
            logging.info(f"Received {amount} stars from user {user_id}. New balance: {new_balance}")


def main() -> None:
    """وظيفة تشغيل البوت."""
    init_db()  # تهيئة قاعدة البيانات عند بدء التشغيل
    application = Application.builder().token(BOT_TOKEN).build()

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
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^👤 Account$"), account_handler))
    application.add_handler(add_fund_conv_handler)
    application.add_handler(wallet_conv_handler)
    
    application.add_handler(MessageHandler(filters.Regex("^🏧 Withdraw$"), withdraw_handler))
    application.add_handler(CallbackQueryHandler(confirm_withdrawal, pattern="^confirm_withdraw$"))
    
    application.add_handler(MessageHandler(filters.ALL, star_transaction_handler))

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
