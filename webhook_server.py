from fastapi import FastAPI, Request
import os
import sys

# Добавляем путь к папке bot, чтобы можно было импортировать твой код
sys.path.append(os.path.join(os.path.dirname(__file__), "bot"))

from bot.main import bot, dp  # Импортируем твой основной бот и диспетчер
from aiogram import types
from bot.payments import yookassa_webhook_fastapi  # Импортируем FastAPI-обработчик для ЮKassa

app = FastAPI()

# Регистрируем эндпоинт для ЮKassa через FastAPI
@app.post("/yookassa/webhook")
async def yookassa_webhook_entrypoint(request: Request):
    return await yookassa_webhook_fastapi(request)

@app.post("/webhook")
async def process_webhook(request: Request):
    data = await request.json()
    update = types.Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

# Для локального запуска через uvicorn:
# uvicorn webhook_server:app --host 0.0.0.0 --port 8080 