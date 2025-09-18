from flask import Flask, request, jsonify
from bot import get_user_data, update_user_data, get_vip_level, application
import os
import asyncio

app = Flask(__name__)
ADMIN_ID = int(os.environ.get("ADMIN_ID", "6172153716"))

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

    # إرسال طلب السحب للأدمن
    vip_level = get_vip_level(user["total_deposits"])
    wallet_address = user["ton_wallet"] or "Not set"
    asyncio.run(application.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📤 New Withdrawal Request\nUser ID: {user_id}\n⭐ Amount: {amount}\nWallet: {wallet_address}\nVIP: {vip_level}\nRemaining Balance: {new_balance}"
    ))
    return jsonify({"status": "ok"})

@app.route("/update_wallet", methods=["POST"])
def update_wallet():
    data = request.json
    user_id = data.get("user_id")
    wallet = data.get("wallet")
    update_user_data(user_id, ton_wallet=wallet)
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(port=5000)
