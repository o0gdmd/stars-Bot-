from flask import Flask, request, jsonify, send_from_directory
import os
import asyncio
from bot import get_user_data, update_user_data, get_vip_level, application

# --- إعداد Flask ---
app = Flask(__name__, static_folder="mini_app")  # ← مجلد Mini App

ADMIN_ID = int(os.environ.get("ADMIN_ID", "6172153716"))

# --- خدمة الملفات الثابتة للـ Mini App ---
@app.route("/mini_app/<path:path>")
def serve_mini_app(path):
    return send_from_directory(app.static_folder, path)

# --- روت للحصول على بيانات المستخدم ---
@app.route("/get_user_data", methods=["POST"])
def get_data():
    data = request.json
    user_id = data.get("user_id")
    user = get_user_data(user_id)
    return jsonify({
        "balance": user["balance"],
        "ton_wallet": user["ton_wallet"],
        "total_deposits": user["total_deposits"],
        "vip_level": get_vip_level(user["total_deposits"])
    })

# --- إضافة Stars للمستخدم ---
@app.route("/add_stars", methods=["POST"])
def add_stars():
    data = request.json
    user_id = data.get("user_id")
    amount = data.get("amount")
    user = get_user_data(user_id)
    new_balance = user["balance"] + amount
    new_total = user["total_deposits"] + amount
    update_user_data(user_id, balance=new_balance, total_deposits=new_total)
    return jsonify({"status": "ok"})

# --- سحب Stars ---
@app.route("/withdraw_stars", methods=["POST"])
def withdraw_stars():
    data = request.json
    user_id = data.get("user_id")
    amount = data.get("amount")
    user = get_user_data(user_id)
    
    if amount > user["balance"]:
        return jsonify({"status": "error", "message": "Insufficient balance"})
    
    new_balance = user["balance"] - amount
    update_user_data(user_id, balance=new_balance)

    # إرسال تفاصيل السحب للأدمن
    vip_level = get_vip_level(user["total_deposits"])
    wallet_address = user["ton_wallet"] or "Not set"
    asyncio.run(application.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📤 New Withdrawal Request\n"
             f"👤 User ID: {user_id}\n"
             f"⭐ Amount: {amount}\n"
             f"💳 Wallet: {wallet_address}\n"
             f"🏅 VIP Level: {vip_level}\n"
             f"💰 Remaining Balance: {new_balance}"
    ))
    return jsonify({"status": "ok"})

# --- تحديث TON Wallet ---
@app.route("/update_wallet", methods=["POST"])
def update_wallet():
    data = request.json
    user_id = data.get("user_id")
    wallet = data.get("wallet")
    update_user_data(user_id, ton_wallet=wallet)
    return jsonify({"status": "ok"})

# --- تشغيل السيرفر ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
