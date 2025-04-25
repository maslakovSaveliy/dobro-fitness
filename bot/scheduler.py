import os
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from datetime import datetime, timedelta
from .db import get_users_for_renewal, update_subscription_until, deactivate_expired_subscriptions
from .payments import charge_subscription

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TELEGRAM_TOKEN)

async def send_reminders():
    async with httpx.AsyncClient() as client:
        three_days_ago = (datetime.utcnow() - timedelta(days=3)).isoformat()
        resp = await client.get(
            f"{os.getenv('SUPABASE_URL')}/rest/v1/users",
            headers={
                "apikey": os.getenv('SUPABASE_KEY'),
                "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}",
            },
            params={"last_active_at": f"lt.{three_days_ago}", "is_paid": "eq.true"}
        )
        users = resp.json()
        for user in users:
            try:
                await bot.send_message(user["telegram_id"], "Давно не было активности! Не забывай про тренировки и питание. Я всегда на связи 💪")
            except Exception as e:
                print(f"Ошибка при отправке напоминания {user.get('telegram_id')}: {e}")

async def auto_charge_expired(bot: Bot):
    users = await get_users_for_renewal()
    for user in users:
        ok, err = await charge_subscription(user["telegram_id"])
        if ok:
            new_until = datetime.utcnow() + timedelta(days=30)
            await update_subscription_until(user["telegram_id"], new_until)
            await bot.send_message(user["telegram_id"], "С вашей карты успешно списана оплата за подписку на месяц. Спасибо!")
        else:
            await bot.send_message(user["telegram_id"], f"Не удалось списать оплату за подписку: {err}. Попробуйте оплатить вручную с помощью /pay.")

async def daily_deactivate_expired():
    await deactivate_expired_subscriptions()

async def scheduler_start():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_reminders, "interval", days=1)
    scheduler.add_job(auto_charge_expired, "interval", days=1, args=[bot])
    scheduler.add_job(daily_deactivate_expired, 'interval', days=1)
    scheduler.start() 