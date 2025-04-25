import os
import openai
import asyncio

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
    prompt = (
        f"Сгенерируй персональную тренировку для пользователя. "
        f"Цель: {user.get('goal', 'не указано')}. "
        f"Уровень: {user.get('level', 'не указано')}. "
        f"Ограничения: {user.get('health_issues', 'нет')}. "
        f"Частота тренировок: {user.get('workouts_per_week', 'не указано')} раз в неделю. "
        f"Рост: {user.get('height', 'не указано')} см. Вес: {user.get('weight', 'не указано')} кг. Возраст: {user.get('age', 'не указано')}. Пол: {user.get('gender', 'не указано')}. "
        f"Дай подробный план тренировки на 1 день. Формат: \n1. ...\n2. ...\n3. ...\n "
        f"Отвечай всегда только на русском языке."
    )
    return await ask_gpt(prompt, "Сгенерируй тренировку")

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