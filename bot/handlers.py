# Здесь будут хендлеры для пользовательских команд и сообщений 
import json
import os
from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, default_state
from .db import (
    create_user, update_user_profile, get_user_by_telegram_id, add_workout, confirm_payment, add_meal, update_last_active,
    get_user_workouts, get_user_meals
)
from .ai import ask_gpt, generate_workout_via_ai, analyze_food_photo_via_ai
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InputFile
from aiogram.types import BufferedInputFile
import io
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side
import httpx
from .payments import create_payment_link

SUBSCRIPTION_AMOUNT = os.getenv("SUBSCRIPTION_AMOUNT", "800")

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Получить новую тренировку")],
        [KeyboardButton(text="Подсчет калорий")],
        [KeyboardButton(text="История")],
    ],
    resize_keyboard=True
)
MENU_BUTTONS = ["Получить новую тренировку", "Подсчет калорий", "История"]

ADMIN_MENU_BUTTON = KeyboardButton(text="Пуш-рассылка")

class ProfileStates(StatesGroup):
    goal = State()
    level = State()
    health_issues = State()
    workouts_per_week = State()
    height = State()
    weight = State()
    age = State()
    gender = State()

class CaloriesStates(StatesGroup):
    waiting_for_photo = State()

class PushStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_audience = State()
    waiting_for_confirm = State()

async def mark_active(message):
    await update_last_active(message.from_user.id)

def is_positive_int(text):
    try:
        value = int(text)
        return value > 0
    except (ValueError, TypeError):
        return False

async def require_payment(message: types.Message, user=None):
    if user is None:
        user = await get_user_by_telegram_id(message.from_user.id)
    if not user or not user.get("is_paid"):
        await message.answer(f"Эта функция доступна только после оплаты подписки (стоимость {SUBSCRIPTION_AMOUNT}₽). Используй /pay для получения доступа.")
        return False
    return True

# --- Хендлеры ---
from aiogram import Router
router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await mark_active(message)
    try:
        user = await get_user_by_telegram_id(message.from_user.id)
        menu = await get_main_menu(message.from_user.id)
        if not user or not user.get("is_paid"):
            user = await create_user(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
            )
            await message.answer(
                "Привет! Я фитнес-бот. Помогу тебе с тренировками, питанием и мотивацией!\n\n"
                "Давай начнем с небольшой анкеты.\n\n"
                "1. Какая у тебя цель? (Похудеть/Набрать массу/Поддерживать форму)",
                reply_markup=menu
            )
            await state.set_state(ProfileStates.goal)
            return
        await message.answer("Добро пожаловать! У тебя активна подписка. Используй меню ниже:", reply_markup=menu)
    except Exception as e:
        await message.answer("Произошла ошибка при обработке команды. Попробуйте позже.")
        print(f"Ошибка в /start: {e}")

@router.message(ProfileStates.goal)
async def process_goal(message: types.Message, state: FSMContext):
    try:
        await state.update_data(goal=message.text)
        await message.answer("2. Какой у тебя уровень подготовки? (Новичок/Средний/Продвинутый)")
        await state.set_state(ProfileStates.level)
    except Exception as e:
        await message.answer("Произошла ошибка. Попробуйте позже.")
        print(f"Ошибка в анкете (goal): {e}")

@router.message(ProfileStates.level)
async def process_level(message: types.Message, state: FSMContext):
    try:
        await state.update_data(level=message.text)
        await message.answer("3. Есть ли ограничения по здоровью?")
        await state.set_state(ProfileStates.health_issues)
    except Exception as e:
        await message.answer("Произошла ошибка. Попробуйте позже.")
        print(f"Ошибка в анкете (level): {e}")

@router.message(ProfileStates.health_issues)
async def process_health_issues(message: types.Message, state: FSMContext):
    try:
        await state.update_data(health_issues=message.text)
        await message.answer("4. Сколько раз в неделю хочешь тренироваться?")
        await state.set_state(ProfileStates.workouts_per_week)
    except Exception as e:
        await message.answer("Произошла ошибка. Попробуйте позже.")
        print(f"Ошибка в анкете (health_issues): {e}")

@router.message(ProfileStates.workouts_per_week)
async def process_workouts_per_week(message: types.Message, state: FSMContext):
    try:
        if not is_positive_int(message.text):
            await message.answer("Пожалуйста, введите целое положительное число (сколько раз в неделю хотите тренироваться)?")
            return
        await state.update_data(workouts_per_week=message.text)
        await message.answer("5. Рост (см)?")
        await state.set_state(ProfileStates.height)
    except Exception as e:
        await message.answer("Произошла ошибка. Попробуйте позже.")
        print(f"Ошибка в анкете (workouts_per_week): {e}")

@router.message(ProfileStates.height)
async def process_height(message: types.Message, state: FSMContext):
    try:
        if not is_positive_int(message.text):
            await message.answer("Пожалуйста, введите целое положительное число (ваш рост в см)?")
            return
        await state.update_data(height=message.text)
        await message.answer("6. Вес (кг)?")
        await state.set_state(ProfileStates.weight)
    except Exception as e:
        await message.answer("Произошла ошибка. Попробуйте позже.")
        print(f"Ошибка в анкете (height): {e}")

@router.message(ProfileStates.weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        if not is_positive_int(message.text):
            await message.answer("Пожалуйста, введите целое положительное число (ваш вес в кг)?")
            return
        await state.update_data(weight=message.text)
        await message.answer("7. Возраст?")
        await state.set_state(ProfileStates.age)
    except Exception as e:
        await message.answer("Произошла ошибка. Попробуйте позже.")
        print(f"Ошибка в анкете (weight): {e}")

@router.message(ProfileStates.age)
async def process_age(message: types.Message, state: FSMContext):
    try:
        if not is_positive_int(message.text):
            await message.answer("Пожалуйста, введите целое положительное число (ваш возраст)?")
            return
        await state.update_data(age=message.text)
        await message.answer("8. Пол (М/Ж)?")
        await state.set_state(ProfileStates.gender)
    except Exception as e:
        await message.answer("Произошла ошибка. Попробуйте позже.")
        print(f"Ошибка в анкете (age): {e}")

@router.message(ProfileStates.gender)
async def process_gender(message: types.Message, state: FSMContext):
    try:
        await state.update_data(gender=message.text)
        data = await state.get_data()
        if not is_positive_int(data.get("workouts_per_week")):
            await message.answer("Пожалуйста, введите целое положительное число (сколько раз в неделю хотите тренироваться)?")
            await state.set_state(ProfileStates.workouts_per_week)
            return
        if not is_positive_int(data.get("height")):
            await message.answer("Пожалуйста, введите целое положительное число (ваш рост в см)?")
            await state.set_state(ProfileStates.height)
            return
        if not is_positive_int(data.get("weight")):
            await message.answer("Пожалуйста, введите целое положительное число (ваш вес в кг)?")
            await state.set_state(ProfileStates.weight)
            return
        if not is_positive_int(data.get("age")):
            await message.answer("Пожалуйста, введите целое положительное число (ваш возраст)?")
            await state.set_state(ProfileStates.age)
            return
        await update_user_profile(
            telegram_id=message.from_user.id,
            goal=data.get("goal"),
            level=data.get("level"),
            health_issues=data.get("health_issues"),
            workouts_per_week=int(data.get("workouts_per_week", 0)),
            height=int(data.get("height", 0)),
            weight=int(data.get("weight", 0)),
            age=int(data.get("age", 0)),
            gender=data.get("gender"),
        )
        user = await get_user_by_telegram_id(message.from_user.id)
        workout_text = await generate_workout_via_ai(user)
        await add_workout(
            user_id=user["id"],
            workout_type="free_trial",
            details=workout_text
        )
        await message.answer(
            "Спасибо! Вот твоя первая бесплатная тренировка:\n\n" +
            workout_text +
            f"\n\nЕсли хочешь получить доступ к персональным тренировкам и другим функциям — оформи подписку! Стоимость подписки: {SUBSCRIPTION_AMOUNT}₽."
        )
        await state.clear()
    except Exception as e:
        await message.answer("Произошла ошибка. Попробуйте позже.")
        print(f"Ошибка в анкете (gender): {e}")

@router.message(Command("pay"))
async def cmd_pay(message: types.Message):
    try:
        pay_url, payment_id = await create_payment_link(
            return_url=f"https://t.me/{os.getenv('BOT_USERNAME', 'your_bot_username')}",
            metadata={"telegram_id": str(message.from_user.id)}
        )
        await message.answer(
            f"Для оплаты подписки (стоимость {SUBSCRIPTION_AMOUNT}₽) перейдите по ссылке: {pay_url}\n\nПосле оплаты напишите администратору или дождитесь подтверждения."
        )
    except Exception as e:
        await message.answer("Ошибка при создании платежа. Попробуйте позже.")
        print(f"Ошибка в /pay: {e}")

@router.message(Command("confirm_payment"))
async def cmd_confirm_payment(message: types.Message):
    user = await get_user_by_telegram_id(message.from_user.id)
    if not user or user.get("role") != "admin":
        await message.answer("Нет доступа. Только для админов.")
        return
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Используй: /confirm_payment <telegram_id>")
        return
    telegram_id = int(parts[1])
    updated = await confirm_payment(telegram_id)
    if updated:
        await message.answer(f"Оплата подтверждена для пользователя {telegram_id}.")
    else:
        await message.answer("Пользователь не найден.")

@router.callback_query(lambda c: c.data == "pay_link")
async def process_pay_link(callback_query: types.CallbackQuery):
    pay_url = "https://yookassa.ru/pay/demo-link"
    await callback_query.message.answer(f"Для доступа ко всем функциям бота оплати подписку (стоимость {SUBSCRIPTION_AMOUNT}₽) по ссылке: {pay_url}\n\nПосле оплаты напиши администратору или дождись подтверждения.")
    await callback_query.answer()

@router.message(F.text == "Получить новую тренировку")
async def get_new_workout(message: types.Message):
    await mark_active(message)
    try:
        user = await get_user_by_telegram_id(message.from_user.id)
        if not await require_payment(message, user):
            return
        await message.answer("Команда принята, обрабатываю...")
        workout_text = await generate_workout_via_ai(user)
        await add_workout(
            user_id=user["id"],
            workout_type="personal",
            details=workout_text
        )
        await message.answer(workout_text, reply_markup=MAIN_MENU)
    except Exception as e:
        await message.answer("Произошла ошибка при получении тренировки. Попробуйте позже.")
        print(f"Ошибка в get_new_workout: {e}")

@router.message(F.text == "Подсчет калорий")
async def start_calories(message: types.Message, state: FSMContext):
    await mark_active(message)
    try:
        user = await get_user_by_telegram_id(message.from_user.id)
        if not await require_payment(message, user):
            return
        await message.answer("Команда принята, обрабатываю...")
        await message.answer("Пожалуйста, отправь фото еды.")
        await state.set_state(CaloriesStates.waiting_for_photo)
    except Exception as e:
        await message.answer("Произошла ошибка при запуске сценария подсчета калорий. Попробуйте позже.")
        print(f"Ошибка в start_calories: {e}")

@router.message(CaloriesStates.waiting_for_photo, F.photo)
async def process_calories_photo(message: types.Message, state: FSMContext):
    await mark_active(message)
    try:
        await message.answer("Команда принята, анализирую фото...")
        user = await get_user_by_telegram_id(message.from_user.id)
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)
        file_path = file.file_path
        TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
        file_url = f'https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}'
        gpt_response = await analyze_food_photo_via_ai(file_url)
        # Пытаемся найти JSON в ответе
        json_start = gpt_response.find('{')
        json_end = gpt_response.rfind('}')
        if json_start != -1 and json_end != -1 and json_end > json_start:
            try:
                data = json.loads(gpt_response[json_start:json_end+1])
                await add_meal(user_id=user["id"], description=data.get("description", "Фото еды"), calories=data.get("calories"))
                await message.answer(f"Описание: {data.get('description', '')}\nКалории: {data.get('calories', '')}", reply_markup=MAIN_MENU)
            except Exception as e:
                await message.answer("Ошибка при разборе ответа ИИ. Попробуйте позже.")
                print(f"Ошибка парсинга JSON из Vision: {e}")
        else:
            await message.answer(gpt_response, reply_markup=MAIN_MENU)
        await state.clear()
    except Exception as e:
        await message.answer("Произошла ошибка при обработке фото. Попробуйте позже.")
        print(f"Ошибка в process_calories_photo: {e}")

@router.message(CaloriesStates.waiting_for_photo)
async def process_calories_not_photo(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, отправь именно фото еды.")

@router.message(F.text == "История")
async def show_history(message: types.Message):
    await mark_active(message)
    menu = await get_main_menu(message.from_user.id)
    try:
        user = await get_user_by_telegram_id(message.from_user.id)
        if not await require_payment(message, user):
            return
        workouts = await get_user_workouts(user["id"])
        meals = await get_user_meals(user["id"])
        wb = openpyxl.Workbook()
        ws1 = wb.active
        ws1.title = "Тренировки"
        ws1.append(["Дата", "Тип", "Описание", "Калории (если есть)"])
        # Стили для заголовков
        header_font = Font(bold=True)
        align_left = Alignment(horizontal="left", vertical="top", wrap_text=True)
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        for cell in ws1[1]:
            cell.font = header_font
            cell.alignment = align_left
            cell.border = thin_border
        for w in workouts:
            ws1.append([
                w.get("date", ""),
                w.get("workout_type", ""),
                w.get("details", ""),
                w.get("calories_burned", "")
            ])
        # Стили для данных
        for row in ws1.iter_rows(min_row=2, max_row=ws1.max_row):
            for cell in row:
                cell.alignment = align_left
                cell.border = thin_border
        # Автоширина
        for col in ws1.columns:
            max_length = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    cell_len = len(str(cell.value)) if cell.value else 0
                    if cell_len > max_length:
                        max_length = cell_len
                except:
                    pass
            ws1.column_dimensions[col_letter].width = max(12, min(max_length + 2, 50))
        ws2 = wb.create_sheet(title="Питание")
        ws2.append(["Дата", "Описание", "Калории"])
        for cell in ws2[1]:
            cell.font = header_font
            cell.alignment = align_left
            cell.border = thin_border
        for m in meals:
            ws2.append([
                m.get("date", ""),
                m.get("description", ""),
                m.get("calories", "")
            ])
        for row in ws2.iter_rows(min_row=2, max_row=ws2.max_row):
            for cell in row:
                cell.alignment = align_left
                cell.border = thin_border
        for col in ws2.columns:
            max_length = 0
            col_letter = col[0].column_letter
            for cell in col:
                try:
                    cell_len = len(str(cell.value)) if cell.value else 0
                    if cell_len > max_length:
                        max_length = cell_len
                except:
                    pass
            ws2.column_dimensions[col_letter].width = max(12, min(max_length + 2, 50))
        file_stream = io.BytesIO()
        wb.save(file_stream)
        file_stream.seek(0)
        excel_file = BufferedInputFile(file_stream.read(), filename="history.xlsx")
        await message.answer_document(
            excel_file,
            caption="Ваша история в формате Excel",
            reply_markup=menu
        )
    except Exception as e:
        await message.answer("Произошла ошибка при формировании Excel-файла. Попробуйте позже.", reply_markup=menu)
        print(f"Ошибка в show_history: {e}")
        
@router.message(F.text == "Пуш-рассылка")
async def push_start(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await message.answer("Введите текст пуш-уведомления:")
    await state.set_state(PushStates.waiting_for_text)

@router.message(PushStates.waiting_for_text)
async def push_text(message: types.Message, state: FSMContext):
    await state.update_data(push_text=message.text)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Всем пользователям", callback_data="push_audience_all")],
            [InlineKeyboardButton(text="Только платным", callback_data="push_audience_paid")],
            [InlineKeyboardButton(text="Только бесплатным", callback_data="push_audience_free")],
        ]
    )
    await message.answer("Кому отправить уведомление?", reply_markup=kb)
    await state.set_state(PushStates.waiting_for_audience)

@router.callback_query(lambda c: c.data.startswith("push_audience_"))
async def push_audience(callback_query: types.CallbackQuery, state: FSMContext):
    audience = callback_query.data.replace("push_audience_", "")
    await state.update_data(push_audience=audience)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подтвердить", callback_data="push_confirm")],
            [InlineKeyboardButton(text="Отмена", callback_data="push_cancel")],
        ]
    )
    text = (await state.get_data()).get("push_text", "")
    audience_str = {
        "all": "всем пользователям",
        "paid": "только платным",
        "free": "только бесплатным"
    }[audience]
    await callback_query.message.answer(f"Текст: {text}\nКому: {audience_str}\n\nПодтвердить рассылку?", reply_markup=kb)
    await state.set_state(PushStates.waiting_for_confirm)
    await callback_query.answer()

@router.callback_query(lambda c: c.data == "push_cancel")
async def push_cancel(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.answer("Рассылка отменена.")
    await callback_query.answer()

@router.callback_query(lambda c: c.data == "push_confirm")
async def push_confirm(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("push_text", "")
    audience = data.get("push_audience", "all")
    await callback_query.message.answer("Рассылка начата...")
    await state.clear()
    # Получаем пользователей
    if audience == "all":
        users = await get_users_by_audience(None)
    else:
        users = await get_users_by_audience(audience)
    count = 0
    errors = 0
    from aiogram import Bot
    bot = callback_query.bot
    for user in users:
        try:
            await bot.send_message(user["telegram_id"], text)
            count += 1
        except Exception as e:
            errors += 1
            print(f"Ошибка отправки {user.get('telegram_id')}: {e}")
    await callback_query.message.answer(f"Рассылка завершена. Успешно: {count}, ошибок: {errors}")
    await callback_query.answer()

@router.message(PushStates.waiting_for_audience)
async def push_waiting_audience_message(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, выберите вариант с помощью кнопок ниже.")

@router.message(PushStates.waiting_for_confirm)
async def push_waiting_confirm_message(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, подтвердите или отмените рассылку с помощью кнопок ниже.")

async def is_admin(telegram_id):
    user = await get_user_by_telegram_id(telegram_id)
    return user and user.get("role") == "admin"

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
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        return resp.json()

@router.message(F.text & ~F.text.in_(MENU_BUTTONS), default_state, flags={"order": 100})
async def universal_ai_handler(message: types.Message, state: FSMContext):
    await mark_active(message)
    print("universal_ai_handler called")
    try:
        user = await get_user_by_telegram_id(message.from_user.id)
        if not await require_payment(message, user):
            return
        await message.answer("Команда принята, думаю...")
        gpt_response = await ask_gpt("", message.text)
        # Пытаемся найти JSON в ответе
        json_start = gpt_response.find('{')
        json_end = gpt_response.rfind('}')
        saved = False
        if json_start != -1 and json_end != -1 and json_end > json_start:
            try:
                data = json.loads(gpt_response[json_start:json_end+1])
                if data.get("type") == "meal":
                    await add_meal(user_id=user["id"], description=data.get("description", ""), calories=data.get("calories"))
                    await message.answer("Записал приём пищи: {} ({} ккал)".format(data.get("description", ""), data.get("calories", "")))
                    saved = True
                elif data.get("type") == "workout":
                    await add_workout(user_id=user["id"], workout_type=data.get("workout_type", "custom"), details=data.get("description", ""), calories_burned=data.get("calories_burned"))
                    await message.answer("Записал тренировку: {}".format(data.get("description", "")))
                    saved = True
            except Exception as e:
                print(f"Ошибка парсинга JSON из ответа GPT: {e}")
        # Отправляем сам ответ ИИ (без JSON)
        if saved:
            # Если был JSON, отправляем только текст до него (совет/комментарий)
            if json_start > 0:
                await message.answer(gpt_response[:json_start].strip())
        else:
            await message.answer(gpt_response)
    except Exception as e:
        await message.answer("Произошла ошибка при обработке запроса к ИИ. Попробуйте позже.")
        print(f"Ошибка в universal_ai_handler: {e}")

@router.message()
async def any_message_handler(message: types.Message, state: FSMContext):
    print(f"DEBUG: message.text = '{message.text}'")
    user = await get_user_by_telegram_id(message.from_user.id)
    if user and not user.get("is_paid"):
        pay_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"Оплатить подписку ({SUBSCRIPTION_AMOUNT}₽)", callback_data="pay_link")]
            ]
        )
        await message.answer(
            f"Чтобы получить доступ к персональным тренировкам и другим функциям, оплати подписку. Стоимость подписки: {SUBSCRIPTION_AMOUNT}₽. После оплаты напиши администратору или дождись подтверждения.",
            reply_markup=pay_keyboard
        )
        return
    if message.text in MENU_BUTTONS:
        return
    await message.answer("Используй команды для работы с ботом.")


# Модифицируем MAIN_MENU для админа
async def get_main_menu(telegram_id):
    if await is_admin(telegram_id):
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Получить новую тренировку")],
                [KeyboardButton(text="Подсчет калорий")],
                [KeyboardButton(text="История")],
                [ADMIN_MENU_BUTTON],
            ],
            resize_keyboard=True
        )
    else:
        return MAIN_MENU 