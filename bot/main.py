import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from .handlers import *
from .handlers import router
from .scheduler import scheduler_start
from .payments import register_yookassa_webhook

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MODE = os.getenv("MODE", "polling")  # по умолчанию polling

bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
dp.include_router(router)

async def on_startup(dispatcher, bot, app=None):
    if app is not None:
        register_yookassa_webhook(app)
    await scheduler_start()

async def main():
    if MODE == "web":
        from aiohttp import web
        app = web.Application()
        dp.startup.register(on_startup)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8080)
        await site.start()
        print("Server started at http://0.0.0.0:8080")
        while True:
            await asyncio.sleep(3600)
    else:
        dp.startup.register(on_startup)
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())