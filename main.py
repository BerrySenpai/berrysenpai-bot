import os
from telegram.ext import ApplicationBuilder, CommandHandler
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Telegram bot setup
app = ApplicationBuilder().token(BOT_TOKEN).build()

async def start(update, context):
    await update.message.reply_text("✅ Bot is alive and running!")

app.add_handler(CommandHandler("start", start))

# Small web server (to keep Choreo happy)
async def handle(request):
    return web.Response(text="Bot is running!")

async def run():
    # run Telegram polling and HTTP server together
    from asyncio import create_task, get_event_loop
    loop = get_event_loop()
    loop.create_task(app.run_polling())
    web_app = web.Application()
    web_app.router.add_get("/", handle)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8000)  # port 8000
    await site.start()
    await loop.create_future()  # keep running

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
