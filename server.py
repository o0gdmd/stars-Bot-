import asyncio
from aiohttp import web
import main  # ملف البوت تبعك (main.py)

async def start_bot_and_server():
    # شغل البوت
    bot_task = asyncio.create_task(main.main())

    # شغل سيرفر ويب
    async def handle(request):
        return web.Response(text="Bot + Server Running ✅")

    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    await site.start()

    # استنى البوت يضل شغال
    await bot_task

if __name__ == "__main__":
    asyncio.run(start_bot_and_server())
