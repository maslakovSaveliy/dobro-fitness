import os
import uuid
from yookassa import Configuration, Payment
from aiohttp import web
import json
from fastapi import Request
from fastapi.responses import PlainTextResponse

async def create_payment_link(amount=None, description=None, return_url=None, metadata=None):
    Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
    Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")
    if amount is None:
        amount = float(os.getenv("SUBSCRIPTION_AMOUNT", "10.00"))
    if description is None:
        description = "Подписка на фитнес-бота"
    payment = Payment.create({
        "amount": {
            "value": str(amount),
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": return_url
        },
        "save_payment_method": False,
        "capture": True,
        "description": description,
        "metadata": metadata or {"order_id": str(uuid.uuid4())},
        "receipt": {
            "customer": {
                "email": "test@example.com"
            },
            "items": [
                {
                    "description": description,
                    "quantity": 1.0,
                    "amount": {
                        "value": str(amount),
                        "currency": "RUB"
                    },
                    "vat_code": 1,
                    "payment_subject": "service",
                    "payment_mode": "full_prepayment"
                }
            ]
        }
    })
    return payment.confirmation.confirmation_url, payment.id

# Заглушка: обновить статус пользователя по payment_id и сохранить payment_method_id
async def update_payment_status(payment_id, paid, payment_method_id=None, telegram_id=None):
    print(f"PAYMENT STATUS: {payment_id} paid={paid} payment_method_id={payment_method_id} telegram_id={telegram_id}")
    if paid and payment_method_id and telegram_id:
        from .db import save_payment_method_id, confirm_payment
        from bot.main import bot
        await save_payment_method_id(telegram_id, payment_method_id)
        await confirm_payment(int(telegram_id))
        await bot.send_message(int(telegram_id), "Ваша подписка успешно оплачена! Спасибо!")
    elif paid and telegram_id:
        from .db import confirm_payment
        from bot.main import bot
        await confirm_payment(int(telegram_id))
        await bot.send_message(int(telegram_id), "Ваша подписка успешно оплачена! Спасибо!")
    # Здесь остальная логика обновления пользователя в БД

# aiohttp webhook handler
async def yookassa_webhook(request):
    body = await request.text()
    data = json.loads(body)
    print(f"YooKassa webhook: {data}")
    if data.get("event") == "payment.succeeded":
        payment_obj = data["object"]
        payment_id = payment_obj["id"]
        payment_method_id = payment_obj.get("payment_method", {}).get("id")
        telegram_id = None
        if "metadata" in payment_obj and "telegram_id" in payment_obj["metadata"]:
            telegram_id = payment_obj["metadata"]["telegram_id"]
        await update_payment_status(payment_id, paid=True, payment_method_id=payment_method_id, telegram_id=telegram_id)
    return web.Response(text="OK")

def register_yookassa_webhook(app):
    app.router.add_post("/yookassa/webhook", yookassa_webhook)

async def charge_subscription(telegram_id, amount=None, description=None):
    from yookassa import Configuration, Payment
    from .db import get_user_by_telegram_id
    Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
    Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")
    if amount is None:
        amount = float(os.getenv("SUBSCRIPTION_AMOUNT", "10.00"))
    if description is None:
        description = "Подписка на фитнес-бота"
    user = await get_user_by_telegram_id(telegram_id)
    payment_method_id = user.get("payment_method_id")
    if not payment_method_id:
        return False, "Нет сохранённого способа оплаты"
    try:
        payment = Payment.create({
            "amount": {
                "value": str(amount),
                "currency": "RUB"
            },
            "payment_method_id": payment_method_id,
            "capture": True, 
            "save_payment_method": True,
            "description": description,
            "metadata": {"telegram_id": str(telegram_id)},
            "receipt": {
                "customer": {
                    "email": user.get("email", "test@example.com")
                },
                "items": [
                    {
                        "description": description,
                        "quantity": 1.0,
                        "amount": {
                            "value": str(amount),
                            "currency": "RUB"
                        },
                        "vat_code": 1,
                        "payment_subject": "service",
                        "payment_mode": "full_prepayment"
                    }
                ]
            }
        })
        if payment.status == "succeeded":
            return True, None
        else:
            return False, f"Статус платежа: {payment.status}"
    except Exception as e:
        return False, str(e)

async def yookassa_webhook_fastapi(request: Request):
    body = await request.body()
    data = json.loads(body)
    print(f"YooKassa webhook: {data}")
    if data.get("event") == "payment.succeeded":
        payment_obj = data["object"]
        payment_id = payment_obj["id"]
        payment_method_id = payment_obj.get("payment_method", {}).get("id")
        telegram_id = None
        if "metadata" in payment_obj and "telegram_id" in payment_obj["metadata"]:
            telegram_id = payment_obj["metadata"]["telegram_id"]
        await update_payment_status(payment_id, paid=True, payment_method_id=payment_method_id, telegram_id=telegram_id)
    return PlainTextResponse("OK") 