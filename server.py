import asyncio
from aiohttp import web
import threading
import main  # ← هذا ملف البوت تبعك (main.py)

# ---- شغل البوت في Thread لحاله ----
def run_bot():
    asyncio.run(main.main())  # يستدعي دالة main() الموجودة عندك

bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

# ---- سيرفر ويب بسيط ----
async def handle(request):
    return web.Response(text="Bot + Server Running ✅")

app = web.Application()
app.router.add_get("/", handle)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=10000)
