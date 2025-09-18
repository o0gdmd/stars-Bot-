import asyncio
from aiohttp import web
import threading
import main  # نستورد ملفك كامل بدون ما نفترض اسم المتغير

# ---- شغل البوت في Thread لحاله ----
def run_bot():
    if hasattr(main, "application"):
        # إذا عندك متغير اسمو application
        asyncio.run(main.application.run_polling())
    elif hasattr(main, "Application"):
        # إذا عندك Application (من النوع الكلاسيكي)
        asyncio.run(main.Application.run_polling())
    elif hasattr(main, "main"):
        # إذا عندك دالة اسمها main() تشغل البوت
        asyncio.run(main.main())
    else:
        raise RuntimeError("⚠️ ما لقيت لا application ولا Application ولا main() بملف main.py")

bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

# ---- سيرفر ويب بسيط ----
async def handle(request):
    return web.Response(text="Bot + Server Running ✅")

app = web.Application()
app.router.add_get("/", handle)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)
