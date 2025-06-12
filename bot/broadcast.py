from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import os
import httpx
from .db import get_user_by_telegram_id
import logging
broadcast_router = Router()

class BroadcastStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_audience = State()
    waiting_for_confirm = State()
    broadcasting = State()

AUDIENCE_MAP = {
    "all": "Всем пользователям",
    "paid": "Только платным",
    "free": "Только бесплатным",
    "test_admins": "Тестовая рассылка (только админам)"
}

# Проверка роли админа
async def is_admin(telegram_id):
    user = await get_user_by_telegram_id(telegram_id)
    return user and user.get("role") == "admin"

# Получение пользователей по аудитории
async def get_users_by_audience(audience):
    url = f"{os.getenv('SUPABASE_URL')}/rest/v1/users"
    headers = {
        "apikey": os.getenv('SUPABASE_KEY'),
        "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}",
    }
    params = {}
    if audience == "paid":
        params = {"is_paid": "eq.true"}
    elif audience == "free":
        params = {"is_paid": "eq.false"}
    elif audience == "test_admins":
        params = {"role": "eq.admin"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        return resp.json()

# Старт рассылки
@broadcast_router.message(F.text == "Пуш-рассылка")
async def push_start(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await message.answer("Введите текст пуш-уведомления:")
    await state.set_state(BroadcastStates.waiting_for_text)

@broadcast_router.message(BroadcastStates.waiting_for_text)
async def push_text(message: types.Message, state: FSMContext):
    await state.update_data(push_text=message.text)
    logging.info("DEBUG: отправляю клавиатуру выбора аудитории")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Всем пользователям", callback_data="broadcast_audience_all")],
            [InlineKeyboardButton(text="Только платным", callback_data="broadcast_audience_paid")],
            [InlineKeyboardButton(text="Только бесплатным", callback_data="broadcast_audience_free")],
            [InlineKeyboardButton(text="Тестовая рассылка (только админам)", callback_data="broadcast_audience_test_admins")],
        ]
    )
    await message.answer("Кому отправить уведомление?", reply_markup=kb)
    await state.set_state(BroadcastStates.waiting_for_audience)

@broadcast_router.callback_query(lambda c: c.data.startswith("broadcast_audience_"))
async def push_audience(callback_query: types.CallbackQuery, state: FSMContext):
    audience = callback_query.data.replace("broadcast_audience_", "")
    await state.update_data(push_audience=audience)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить", callback_data="broadcast_confirm")],
            [InlineKeyboardButton(text="Отмена", callback_data="broadcast_cancel")],
        ]
    )
    data = await state.get_data()
    text = data.get("push_text", "")
    audience_str = AUDIENCE_MAP.get(audience, audience)
    note = "\n\n<b>Внимание: рассылка будет отправлена только администраторам!</b>" if audience == "test_admins" else ""
    await callback_query.message.answer(f"Текст: {text}\nКому: {audience_str}{note}\n\nПодтвердить рассылку?", reply_markup=kb, parse_mode="HTML")
    await state.set_state(BroadcastStates.waiting_for_confirm)
    await callback_query.answer()

@broadcast_router.callback_query(lambda c: c.data == "broadcast_cancel")
async def push_cancel(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.answer("Рассылка отменена.")
    await callback_query.answer()

@broadcast_router.callback_query(lambda c: c.data == "broadcast_confirm")
async def push_confirm(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    data = await state.get_data()
    if data.get("is_busy"):
        await callback_query.message.answer("Рассылка уже выполняется, подождите...")
        return
    await state.update_data(is_busy=True)
    text = data.get("push_text", "")
    audience = data.get("push_audience", "all")
    await callback_query.message.answer("Рассылка начата... (вы получите отчёт по завершении)")
    await state.clear()
    # Запуск асинхронной рассылки
    asyncio.create_task(broadcast_worker(callback_query.bot, callback_query.from_user.id, text, audience))

async def broadcast_worker(bot, admin_id, text, audience):
    try:
        users = await get_users_by_audience(audience if audience != "all" else None)
        count = 0
        errors = 0
        total = len(users)
        for idx, user in enumerate(users, 1):
            try:
                await bot.send_message(user["telegram_id"], text)
                count += 1
            except Exception as e:
                errors += 1
                logging.warning(f"Ошибка отправки пользователю {user.get('telegram_id')} ({user.get('username')}): {e}")
            if idx % 100 == 0:
                await bot.send_message(admin_id, f"Рассылка: отправлено {idx} из {total}")
            await asyncio.sleep(0.03)  # ~33 сообщения/сек
        if audience == "test_admins":
            await bot.send_message(admin_id, f"Тестовая рассылка завершена. Успешно: {count}, ошибок: {errors}")
        else:
            await bot.send_message(admin_id, f"Рассылка завершена. Успешно: {count}, ошибок: {errors}")
    except Exception as e:
        await bot.send_message(admin_id, f"Ошибка при рассылке: {e}") 