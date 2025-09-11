import logging
import os
import sqlite3
from telegram import (
    Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, LabeledPrice
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)

# إعداد السجل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# حالات المحادثة
ADD_STARS_STATE, SET_WALLET_STATE = range(2)

# --- قاعدة البيانات ---
def init_db():
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
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    for key, value in kwargs.items():
        cursor.execute(f'UPDATE users SET {key} = ? WHERE user_id = ?', (value, user_id))
    conn.commit()
    conn.close()

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

# --- Add Fund ---
async def add_fund_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("How many Stars do you want to add? (min: 100):")
    return ADD_STARS_STATE

async def get_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        stars_amount = int(update.message.text)
        if stars_amount < 100:
            await update.message.reply_text("The minimum amount is 100 stars. Please enter a valid number:")
            return ADD_STARS_STATE

        # إرسال الفاتورة الرسمية للنجوم
        prices = [LabeledPrice("Stars", stars_amount)]  # القيمة = عدد النجوم مباشرة
        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title="Buy Stars",
            description=f"Adding {stars_amount} Stars to your balance",
            payload=str(stars_amount),   # نخزن المبلغ بالـ payload
            provider_token="",           # مش مطلوب للـ Stars
            currency="XTR",              # XTR = Telegram Stars
            prices=prices
        )
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("Invalid input. Please enter a number:")
        return ADD_STARS_STATE

# --- Payment Handlers ---
async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """لازم الموافقة على الدفع قبل ما يتم"""
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """لما ينجح الدفع"""
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    stars_amount = int(payment.total_amount)  # عدد النجوم المدفوعة

    user_info = get_user_data(user_id)
    new_balance = user_info['balance'] + stars_amount
    update_user_data(user_id, balance=new_balance)

    await update.message.reply_text(
        f"✅ Payment successful!\n"
        f"Added {stars_amount} Stars to your balance.\n"
        f"Current balance: {new_balance} Stars."
    )
    logging.info(f"User {user_id} paid {stars_amount} Stars. New balance: {new_balance}")

# --- Withdraw ---
async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

async def confirm_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_info = get_user_data(user_id)

    if user_info['ton_wallet'] is None:
        await query.edit_message_text("Error: Please set your TON Wallet address first using the 'Wallet' button.")
        return
        
    await query.edit_message_text("Your withdrawal request has been submitted successfully. The TON will be sent to your wallet shortly.")
    update_user_data(user_id, balance=0)

# --- Wallet ---
async def wallet_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_info = get_user_data(update.effective_user.id)
    
    current_wallet = user_info['ton_wallet'] if user_info['ton_wallet'] else "Not set"
    await update.message.reply_text(f"Your current TON wallet is: `{current_wallet}`\nPlease send me your new TON wallet address to save it:", parse_mode='Markdown')
    return SET_WALLET_STATE

async def set_ton_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    new_wallet = update.message.text
    
    if not (new_wallet.startswith(("EQ", "UQ")) or new_wallet.endswith((".ton",))):
        await update.message.reply_text("Invalid TON wallet address. Please send a valid one.")
        return SET_WALLET_STATE
        
    update_user_data(user_id, ton_wallet=new_wallet)
    await update.message.reply_text(f"Your new TON wallet has been saved: `{new_wallet}`", parse_mode='Markdown')
    return ConversationHandler.END

# --- Star Transactions (optional fallback) ---
async def star_transaction_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

# --- Main ---
def main() -> None:
    init_db()
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

    # Handlers الدفع
    application.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler))

    # fallback للـ Stars transactions
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
