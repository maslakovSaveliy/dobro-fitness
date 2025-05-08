import os
import openai
import asyncio
from openai import AsyncOpenAI
from .db import get_user_workouts

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

async def ask_gpt(prompt, user_message):
    messages = [
        {"role": "system", "content": (
            "Ты фитнес-бот. Если пользователь сообщает о приёме пищи или тренировке, верни JSON с типом и деталями (пример: {\"type\": \"meal\", \"description\": \"...\", \"calories\": 350} или {\"type\": \"workout\", ...}). "
            "Если это просто вопрос — дай совет. Если ничего не нужно сохранять — просто ответь. "
            "Отвечай всегда только на русском языке."
        )},
        {"role": "user", "content": user_message}
    ]
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.4,
            max_tokens=500
        )
    )
    return response.choices[0].message.content

async def generate_workout_via_ai(user):
    # Получаем последние 2-3 тренировки пользователя
    workouts = await get_user_workouts(user["id"], limit=3)
    last_exercises = []
    for w in workouts:
        details = w.get("details", "").strip()
        if details:
            first_line = details.split("\n")[0].strip()
            if first_line:
                last_exercises.append(first_line)
    history_str = ", ".join(last_exercises)
    unique_exercises = list({ex for ex in last_exercises if ex})
    used_exercises_str = ", ".join(unique_exercises)
    if history_str:
        history_prompt = f"Последние тренировки: {history_str}."
    else:
        history_prompt = ""
    if used_exercises_str:
        used_prompt = f"Уже использованные упражнения: {used_exercises_str}."
    else:
        used_prompt = ""

    # Список упражнений для разнообразия
    variety_exercises = [
        "Приседания с гантелями",
        "Выпады назад",
        "Болгарские сплит-приседания",
        "Жим гантелей сидя",
        "Разведения гантелей в стороны",
        "Тяга гантели к поясу",
        "Подтягивания обратным хватом",
        "Планка с подъёмом ноги",
        "Скручивания на фитболе",
        "Велотренажёр",
        "Бёрпи",
        "Фермерская прогулка",
        "Махи гирей",
        "Отжимания на брусьях",
        "Подъём корпуса на скамье",
        "Гиперэкстензия",
        "Сумо-приседания",
        "Жим штанги стоя",
        "Разгибания ног в тренажёре",
        "Сгибания рук с гантелями",
        "Кардио: бег, эллипс, скакалка, ходьба в гору"
    ]
    variety_str = ", ".join(variety_exercises)

    prompt = (
        f"Сгенерируй персональный план тренировки на сегодня для пользователя с учётом его цели, уровня, ограничений, частоты тренировок, роста, веса, возраста и пола.\n"
        f"Цель: {user.get('goal', 'не указано')}. "
        f"Уровень: {user.get('level', 'не указано')}. "
        f"Ограничения: {user.get('health_issues', 'нет')}. "
        f"Частота тренировок: {user.get('workouts_per_week', 'не указано')} раз в неделю. "
        f"Рост: {user.get('height', 'не указано')} см. Вес: {user.get('weight', 'не указано')} кг. Возраст: {user.get('age', 'не указано')}. Пол: {user.get('gender', 'не указано')}. "
        f"{history_prompt}\n"
        f"{used_prompt}\n"
        f"Вот список упражнений, которые можно использовать для разнообразия: {variety_str}.\n"
        f"Выбери хотя бы 2 упражнения из этого списка, которых не было в последних тренировках пользователя. Остальные упражнения подбирай исходя из цели, уровня и баланса по группам мышц. Не используй упражнения из истории, кроме базовых (присед, жим, тяга) — их можно оставить, но не более 1-2 за тренировку. Сделай тренировку максимально разнообразной и сбалансированной по группам мышц.\n"
        f"Форматируй ответ строго так:\n"
        f"План тренировки на сегодня\n\n"
        f"1. [Название упражнения]\n[кол-во подходов × повторений — вес]\n*Комментарий по технике или совет*\n\n2. ...\n...\n6. [Кардио/заминка]\n[время/интенсивность]\n*Комментарий*\n\nНе добавляй лишних пояснений вне структуры плана."
    )

    # Временное логирование для отладки
    print("USER DATA:", user)
    print("PROMPT FOR GPT:\n", prompt)

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Ты фитнес-бот. Отвечай всегда только на русском языке."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=700
    )
    return response.choices[0].message.content

async def generate_workout_via_ai_with_history(user, history):
    # Список упражнений для разнообразия
    variety_exercises = [
        "Приседания с гантелями",
        "Выпады назад",
        "Болгарские сплит-приседания",
        "Жим гантелей сидя",
        "Разведения гантелей в стороны",
        "Тяга гантели к поясу",
        "Подтягивания обратным хватом",
        "Планка с подъёмом ноги",
        "Скручивания на фитболе",
        "Велотренажёр",
        "Бёрпи",
        "Фермерская прогулка",
        "Махи гирей",
        "Отжимания на брусьях",
        "Подъём корпуса на скамье",
        "Гиперэкстензия",
        "Сумо-приседания",
        "Жим штанги стоя",
        "Разгибания ног в тренажёре",
        "Сгибания рук с гантелями",
        "Кардио: бег, эллипс, скакалка, ходьба в гору"
    ]
    variety_str = ", ".join(variety_exercises)

    system_prompt = (
        f"Ты фитнес-бот. Отвечай всегда только на русском языке.\n"
        f"Сгенерируй персональный план тренировки на сегодня для пользователя с учётом его цели, уровня, ограничений, частоты тренировок, роста, веса, возраста и пола.\n"
        f"Цель: {user.get('goal', 'не указано')}. "
        f"Уровень: {user.get('level', 'не указано')}. "
        f"Ограничения: {user.get('health_issues', 'нет')}. "
        f"Частота тренировок: {user.get('workouts_per_week', 'не указано')} раз в неделю. "
        f"Рост: {user.get('height', 'не указано')} см. Вес: {user.get('weight', 'не указано')} кг. Возраст: {user.get('age', 'не указано')}. Пол: {user.get('gender', 'не указано')}. "
        f"Вот список упражнений, которые можно использовать для разнообразия: {variety_str}.\n"
        f"Выбери хотя бы 2 упражнения из этого списка, которых не было в последних тренировках пользователя. Остальные упражнения подбирай исходя из цели, уровня и баланса по группам мышц. Не используй упражнения из истории, кроме базовых (присед, жим, тяга) — их можно оставить, но не более 1-2 за тренировку. Сделай тренировку максимально разнообразной и сбалансированной по группам мышц.\n"
        f"Форматируй ответ строго так:\n"
        f"План тренировки на сегодня\n\n"
        f"1. [Название упражнения]\n[кол-во подходов × повторений — вес]\n*Комментарий по технике или совет*\n\n2. ...\n...\n6. [Кардио/заминка]\n[время/интенсивность]\n*Комментарий*\n\nНе добавляй лишних пояснений вне структуры плана."
    )
    messages = [{"role": "system", "content": system_prompt}] + history
    print("PROMPT HISTORY FOR GPT:", messages)
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.4,
        max_tokens=700
    )
    return response.choices[0].message.content

async def analyze_food_photo_via_ai(file_url):
    prompt = (
        "Определи, что изображено на фото, и оцени калорийность блюда. Верни JSON вида: {\"description\": \"...\", \"calories\": ...}. Отвечай всегда только на русском языке."
    )
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": file_url}}
                ]}
            ],
            max_tokens=500
        )
    )
    return response.choices[0].message.content 