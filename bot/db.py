import os
import httpx
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_API = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

async def get_user_by_telegram_id(telegram_id: int):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_API}/users",
            params={"telegram_id": f"eq.{telegram_id}"},
            headers=HEADERS
        )
        data = resp.json()
        return data[0] if data else None

async def create_user(telegram_id: int, username: str = None, first_name: str = None, last_name: str = None):
    user = await get_user_by_telegram_id(telegram_id)
    if user:
        return user
    payload = [{
        "telegram_id": telegram_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
    }]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SUPABASE_API}/users",
            headers=HEADERS,
            json=payload,
        )
        data = resp.json()
        return data[0] if data else None

async def update_user_profile(telegram_id: int, **fields):
    if not fields:
        return None
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{SUPABASE_API}/users",
            params={"telegram_id": f"eq.{telegram_id}"},
            headers=HEADERS,
            json=fields
        )
        data = resp.json()
        return data[0] if data else None

async def add_workout(user_id: str, workout_type: str, details: str, date=None, calories_burned=None):
    from datetime import date as dt_date
    if date is None:
        date = dt_date.today().isoformat()
    data = {
        "user_id": user_id,
        "date": date,
        "workout_type": workout_type,
        "details": details,
    }
    if calories_burned is not None:
        data["calories_burned"] = calories_burned
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SUPABASE_API}/workouts",
            headers=HEADERS,
            json=[data]
        )
        print("add_workout status:", resp.status_code)
        print("add_workout text:", resp.text)
        data = resp.json()
        return data[0] if data else None

async def has_free_trial(telegram_id: int):
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        return False
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_API}/workouts",
            params={"user_id": f"eq.{user['id']}", "workout_type": "eq.free_trial"},
            headers=HEADERS
        )
        data = resp.json()
        return bool(data)

async def confirm_payment(telegram_id: int, days: int = 30):
    paid_until = (datetime.utcnow() + timedelta(days=days)).isoformat()
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{SUPABASE_API}/users",
            params={"telegram_id": f"eq.{telegram_id}"},
            headers=HEADERS,
            json={"is_paid": True, "paid_until": paid_until}
        )
        data = resp.json()
        return data[0] if data else None

async def add_meal(user_id: str, description: str, calories: int = None, date=None, photo_url=None):
    from datetime import date as dt_date
    if date is None:
        date = dt_date.today().isoformat()
    data = {
        "user_id": user_id,
        "date": date,
        "description": description,
    }
    if calories is not None:
        data["calories"] = calories
    if photo_url is not None:
        data["photo_url"] = photo_url
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SUPABASE_API}/meals",
            headers=HEADERS,
            json=[data]
        )
        return resp.status_code == 201

async def update_last_active(telegram_id: int):
    from datetime import datetime
    now = datetime.utcnow().isoformat()
    async with httpx.AsyncClient() as client:
        await client.patch(
            f"{SUPABASE_API}/users",
            params={"telegram_id": f"eq.{telegram_id}"},
            headers=HEADERS,
            json={"last_active_at": now}
        )

async def get_user_workouts(user_id: str, limit: int = 10):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_API}/workouts",
            params={
                "user_id": f"eq.{user_id}",
                "order": "date.desc",
                "limit": str(limit)
            },
            headers=HEADERS
        )
        return resp.json()

async def get_user_meals(user_id: str, limit: int = 10):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_API}/meals",
            params={
                "user_id": f"eq.{user_id}",
                "order": "date.desc",
                "limit": str(limit)
            },
            headers=HEADERS
        )
        return resp.json()

async def get_users_for_renewal():
    url = f"{os.getenv('SUPABASE_URL')}/rest/v1/users"
    headers = {
        "apikey": os.getenv('SUPABASE_KEY'),
        "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}",
    }
    today = datetime.utcnow().date().isoformat()
    params = {
        "subscription_until": f"lte.{today}",
        "payment_method_id": "not.is.null"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, params=params)
        return resp.json()

async def update_subscription_until(telegram_id, new_until):
    url = f"{os.getenv('SUPABASE_URL')}/rest/v1/users"
    headers = {
        "apikey": os.getenv('SUPABASE_KEY'),
        "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}",
        "Content-Type": "application/json"
    }
    data = {"subscription_until": new_until.isoformat()}
    params = {"telegram_id": f"eq.{telegram_id}"}
    async with httpx.AsyncClient() as client:
        await client.patch(url, headers=headers, params=params, json=data)

async def deactivate_expired_subscriptions():
    today = datetime.utcnow().date().isoformat()
    async with httpx.AsyncClient() as client:
        # Получаем всех пользователей с истекшей подпиской
        resp = await client.get(
            f"{SUPABASE_API}/users",
            params={"paid_until": f"lt.{today}", "is_paid": "eq.true"},
            headers=HEADERS
        )
        users = resp.json()
        for user in users:
            await client.patch(
                f"{SUPABASE_API}/users",
                params={"telegram_id": f"eq.{user['telegram_id']}"},
                headers=HEADERS,
                json={"is_paid": False}
            )

async def save_payment_method_id(telegram_id: int, payment_method_id: str):
    url = f"{os.getenv('SUPABASE_URL')}/rest/v1/users"
    headers = {
        "apikey": os.getenv('SUPABASE_KEY'),
        "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}",
        "Content-Type": "application/json"
    }
    data = {"payment_method_id": payment_method_id}
    params = {"telegram_id": f"eq.{telegram_id}"}
    async with httpx.AsyncClient() as client:
        await client.patch(url, headers=headers, params=params, json=data) 