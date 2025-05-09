from fastapi import FastAPI, Request
import os
import sys
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), "bot"))

from bot.main import bot, dp 
from aiogram import types
from bot.payments import yookassa_webhook_fastapi 
from bot.scheduler import scheduler_start

app = FastAPI()

@app.post("/yookassa/webhook")
async def yookassa_webhook_entrypoint(request: Request):
    return await yookassa_webhook_fastapi(request)

@app.post("/webhook")
async def process_webhook(request: Request):
    data = await request.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    logging.info("Запуск планировщика задач...")
    await scheduler_start()
    logging.info("Планировщик задач успешно запущен.")

# Для локального запуска через uvicorn:
# uvicorn webhook_server:app --host 0.0.0.0 --port 8080 