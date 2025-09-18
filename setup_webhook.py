import os
import asyncio
from telegram.ext import Application

# Get environment variables
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

async def set_bot_webhook():
    """Sets the bot's webhook URL to the Render URL."""
    if not RENDER_URL:
        print("RENDER_EXTERNAL_URL environment variable is not set. Cannot set webhook.")
        return

    application = Application.builder().token(BOT_TOKEN).build()
    webhook_url = f"{RENDER_URL}/{BOT_TOKEN}"
    print(f"Attempting to set webhook to: {webhook_url}")

    try:
        await application.bot.set_webhook(url=webhook_url)
        print("✅ Webhook has been set successfully!")
    except Exception as e:
        print(f"❌ Failed to set webhook. Error: {e}")

if __name__ == '__main__':
    asyncio.run(set_bot_webhook())
