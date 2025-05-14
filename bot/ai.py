import os
import openai
import asyncio
from openai import AsyncOpenAI
from .db import get_user_workouts
import re
import random

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

async def ask_gpt(prompt, user_message):
    messages = [
        {"role": "system", "content": (
            "Ты фитнес-бот. Если пользователь сообщает о приёме пищи или тренировке, верни JSON с типом и деталями (пример: {\"type\": \"meal\", \"description\": \"...\", \"calories\": 350, \"proteins\": ..., \"fats\": ..., \"carbs\": ...} или {\"type\": \"workout\", ...}). Обязательно указывай БЖУ (белки, жиры, углеводы) в граммах. "
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
    n = random.randint(5, 8)
    # Получаем последние 2-3 тренировки пользователя
    workouts = await get_user_workouts(user["id"], limit=3)
    last_exercises = []
    def extract_exercise_names(details):
        lines = details.split('\n')
        exercises = []
        for line in lines:
            match = re.match(r'\d+\.\s*([^\n]+)', line)
            if match:
                exercises.append(match.group(1).strip())
        return exercises
    for w in workouts:
        details = w.get("details", "").strip()
        if details:
            exercises = extract_exercise_names(details)
            last_exercises.extend(exercises)
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

    prompt = (
        f"Ты - профессиональный фитнесс-тренер. Генерируй разнообразный персональный план тренировок для пользователя с учётом его цели, уровня, ограничений, частоты тренировок, роста, веса, возраста, пола и места занятий.\n"
        f"Цель: {user.get('goal', 'не указано')}. "
        f"Уровень: {user.get('level', 'не указано')}. "
        f"Ограничения: {user.get('health_issues', 'нет')}. "
        f"Место занятий: {user.get('location', 'не указано')}. "
        f"Частота тренировок: {user.get('workouts_per_week', 'не указано')} раз в неделю. "
        f"Рост: {user.get('height', 'не указано')} см. Вес: {user.get('weight', 'не указано')} кг. Возраст: {user.get('age', 'не указано')}. Пол: {user.get('gender', 'не указано')}. "
        f"{history_prompt}\n"
        f"{used_prompt}\n"
        f"Не используй ни одно упражнение из списка последних тренировок, даже базовые: {used_exercises_str}. Составь тренировку только из новых упражнений. Сделай тренировку максимально разнообразной и сбалансированной по группам мышц.\n"
        f"Сгенерируй ровно {n} упражнений (последнее — кардио или заминка).\n"
        f"Для каждого упражнения обязательно указывай вес (даже если это собственный вес — пиши явно). После плана тренировки выдай отдельным абзацем совет по питанию на сегодня с обязательным указанием БЖУ (белки, жиры, углеводы).\n"
        f"Форматируй ответ строго так:\n"
        f"План тренировки на сегодня\n\n"
        f"Для каждого упражнения используй такой формат:\n"
        f"[Номер]. [Название упражнения]\n[кол-во подходов × повторений — вес]\n*Комментарий по технике или совет*\n\n"
        f"Последнее упражнение всегда кардио или заминка, указывай его в том же формате.\n"
        f"Совет по питанию: ... (Б: ... г, Ж: ... г, У: ... г)\n\nНе добавляй лишних пояснений вне структуры плана."
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
        max_tokens=1200
    )
    return response.choices[0].message.content

async def generate_workout_via_ai_with_history(user, history):
    n = random.randint(5, 8)
    # Извлекаем историю упражнений из последних тренировок для промпта
    workouts = await get_user_workouts(user["id"], limit=3)
    last_exercises = []
    def extract_exercise_names(details):
        lines = details.split('\n')
        exercises = []
        for line in lines:
            match = re.match(r'\d+\.\s*([^\n]+)', line)
            if match:
                exercises.append(match.group(1).strip())
        return exercises
    for w in workouts:
        details = w.get("details", "").strip()
        if details:
            exercises = extract_exercise_names(details)
            last_exercises.extend(exercises)
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

    system_prompt = (
        f"Ты - профессиональный фитнесс-тренер. Генерируй разнообразный персональный план тренировок для пользователя с учётом его цели, уровня, ограничений, частоты тренировок, роста, веса, возраста, пола и места занятий.\n"
        f"Цель: {user.get('goal', 'не указано')}. "
        f"Уровень: {user.get('level', 'не указано')}. "
        f"Ограничения: {user.get('health_issues', 'нет')}. "
        f"Место занятий: {user.get('location', 'не указано')}. "
        f"Частота тренировок: {user.get('workouts_per_week', 'не указано')} раз в неделю. "
        f"Рост: {user.get('height', 'не указано')} см. Вес: {user.get('weight', 'не указано')} кг. Возраст: {user.get('age', 'не указано')}. Пол: {user.get('gender', 'не указано')}. "
        f"{history_prompt}\n"
        f"{used_prompt}\n"
        f"Не используй ни одно упражнение из списка последних тренировок, даже базовые: {used_exercises_str}. Составь тренировку только из новых упражнений. Сделай тренировку максимально разнообразной и сбалансированной по группам мышц.\n"
        f"Сгенерируй ровно {n} упражнений (последнее — кардио или заминка).\n"
        f"Для каждого упражнения обязательно указывай вес (даже если это собственный вес — пиши явно). После плана тренировки выдай отдельным абзацем совет по питанию на сегодня с обязательным указанием БЖУ (белки, жиры, углеводы).\n"
        f"Форматируй ответ строго так:\n"
        f"План тренировки на сегодня\n\n"
        f"Для каждого упражнения используй такой формат:\n"
        f"[Номер]. [Название упражнения]\n[кол-во подходов × повторений — вес]\n*Комментарий по технике или совет*\n\n"
        f"Последнее упражнение всегда кардио или заминка, указывай его в том же формате.\n"
        f"Совет по питанию: ... (Б: ... г, Ж: ... г, У: ... г)\n\nНе добавляй лишних пояснений вне структуры плана."
    )
    messages = [{"role": "system", "content": system_prompt}] + history
    print("PROMPT HISTORY FOR GPT:", messages)
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.4,
        max_tokens=1200
    )
    return response.choices[0].message.content

async def analyze_food_photo_via_ai(file_url):
    prompt = (
        "Определи, что изображено на фото, и оцени калорийность блюда. Верни JSON вида: {\"description\": \"...\", \"calories\": ..., \"proteins\": ..., \"fats\": ..., \"carbs\": ...}. Обязательно укажи БЖУ (белки, жиры, углеводы) в граммах. Отвечай всегда только на русском языке."
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