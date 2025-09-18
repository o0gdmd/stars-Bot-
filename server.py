import asyncio
from aiohttp import web
import threading
from main import application  # ← جاي من main.py مباشرة

# ---- شغل البوت في Thread لحاله ----
def run_bot():
    asyncio.run(application.run_polling())  # شغل البوت من غير ما نحتاج main()

bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

# ---- سيرفر ويب بسيط ----
async def handle(request):
    return web.Response(text="Bot + Server Running ✅")

app = web.Application()
app.router.add_get("/", handle)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render يحط البورت بالمتغير PORT
    web.run_app(app, host="0.0.0.0", port=port)
