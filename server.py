import asyncio
from aiohttp import web
import threading
import main  # استورد ملفك كامل بدون ما تحدد متغير

# ---- شغل البوت في Thread مستقل ----
def run_bot():
    # إذا عندك دالة main() هي اللي بتشغّل البوت
    if hasattr(main, "main"):
        asyncio.run(main.main())
    else:
        raise RuntimeError("⚠️ لازم يكون عندك دالة اسمها main() بملف main.py")

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
