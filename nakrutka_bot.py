import base64
import hashlib
import json
import os
import logging
from datetime import datetime

import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

logging.basicConfig(level=logging.INFO)

# Telegram & API
API_TOKEN = os.getenv("API_TOKEN")
SMM_API_KEY = os.getenv("SMM_API_KEY")
LIQPAY_PUBLIC_KEY = os.getenv("LIQPAY_PUBLIC_KEY")
LIQPAY_PRIVATE_KEY = os.getenv("LIQPAY_PRIVATE_KEY")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", f"https://nakrutkabot-qmxh.onrender.com{WEBHOOK_PATH}")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

USERS_FILE = "users.json"
orders = {}

class OrderState(StatesGroup):
    category = State()
    service = State()
    quantity = State()
    confirm = State()

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def update_user_balance(user_id, amount):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {"balance": 0}
    users[uid]["balance"] += amount
    save_users(users)

def get_user_balance(user_id):
    users = load_users()
    return users.get(str(user_id), {}).get("balance", 0)

def create_payment_link(amount, user_id):
    order_id = f"{user_id}_{int(datetime.now().timestamp())}"
    data = {
        "public_key": LIQPAY_PUBLIC_KEY,
        "version": "3",
        "action": "pay",
        "amount": str(amount),
        "currency": "UAH",
        "description": f"Поповнення балансу для користувача {user_id}",
        "order_id": order_id,
        "sandbox": 1,
        "server_url": os.getenv("LIQPAY_CALLBACK_URL", "https://example.com/liqpay-callback")
    }
    data_str = base64.b64encode(json.dumps(data).encode()).decode()
    sign_str = LIQPAY_PRIVATE_KEY + data_str + LIQPAY_PRIVATE_KEY
    signature = base64.b64encode(hashlib.sha1(sign_str.encode()).digest()).decode()
    return f"https://www.liqpay.ua/api/3/checkout?data={data_str}&signature={signature}", order_id, amount

def fetch_services():
    try:
        r = requests.post("https://nakrutka.cc/api/v2", json={
            "key": SMM_API_KEY,
            "action": "services"
        })
        return r.json()
    except Exception as e:
        logging.error(f"Помилка при отриманні послуг: {e}")
        return []

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/balance")],
            [KeyboardButton(text="/popovnyty")],
            [KeyboardButton(text="/services")]
        ],
        resize_keyboard=True
    )
    await message.answer("👋 Вітаю! Оберіть команду:", reply_markup=kb)

@dp.message(F.text == "/balance")
async def cmd_balance(message: types.Message):
    bal = get_user_balance(message.from_user.id)
    await message.answer(f"💳 Ваш баланс: {bal:.2f} грн")

@dp.message(F.text == "/popovnyty")
async def cmd_topup(message: types.Message):
    kb = InlineKeyboardMarkup()
    for amt in [50, 100, 200]:
        url, order_id, amount = create_payment_link(amt, message.from_user.id)
        orders[order_id] = {"user_id": message.from_user.id, "amount": amount}
        kb.add(InlineKeyboardButton(text=f"💸 Поповнити на {amt} грн", url=url))
    await message.answer("Оберіть суму поповнення:", reply_markup=kb)

@dp.message(F.text == "/services")
async def list_categories(message: types.Message, state: FSMContext):
    services = fetch_services()
    if not services:
        await message.answer("⚠️ Не вдалося отримати список послуг.")
        return
    categories = sorted(set(s["category"] for s in services))
    kb = InlineKeyboardMarkup()
    for cat in categories:
        kb.add(InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}"))
    await message.answer("📂 Виберіть категорію:", reply_markup=kb)
    await state.set_state(OrderState.category)

@dp.callback_query(F.data.startswith("cat_"))
async def choose_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data[4:]
    services = fetch_services()
    filtered = [s for s in services if s["category"] == category][:10]
    kb = InlineKeyboardMarkup()
    for s in filtered:
        kb.add(InlineKeyboardButton(
            text=f'{s["name"]} ({s["rate"]} грн/1000)', 
            callback_data=f'svc_{s["service"]}'
        ))
    await callback.message.edit_text(f"🔽 Послуги в категорії *{category}*:", parse_mode="Markdown", reply_markup=kb)
    await state.update_data(all_services=services)
    await state.set_state(OrderState.service)

@dp.callback_query(F.data.startswith("svc_"))
async def choose_service(callback: types.CallbackQuery, state: FSMContext):
    service_id = int(callback.data[4:])
    data = await state.get_data()
    service = next((s for s in data["all_services"] if s["service"] == service_id), None)
    if not service:
        await callback.message.answer("⚠️ Послугу не знайдено.")
        return
    await state.update_data(selected_service=service)
    await callback.message.answer(f"Введіть кількість (мінімум {service['min']}, максимум {service['max']}):")
    await state.set_state(OrderState.quantity)

@dp.message(OrderState.quantity)
async def enter_quantity(message: types.Message, state: FSMContext):
    qty = message.text.strip()
    if not qty.isdigit():
        return await message.answer("❗ Введіть число.")
    qty = int(qty)
    data = await state.get_data()
    service = data["selected_service"]
    if qty < service["min"] or qty > service["max"]:
        return await message.answer(f"⚠️ Мінімум: {service['min']}, максимум: {service['max']}")
    total = round((qty / 1000) * service["rate"], 2)
    await state.update_data(qty=qty, total=total)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити", callback_data="confirm_order")],
        [InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel_order")]
    ])
    await message.answer(f"💡 Ви обрали:
*{service['name']}*
Кількість: {qty}
Ціна: {total} грн", parse_mode="Markdown", reply_markup=kb)
    await state.set_state(OrderState.confirm)

@dp.callback_query(F.data == "confirm_order")
async def confirm(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    balance = get_user_balance(user_id)
    if balance < data["total"]:
        return await callback.message.answer("❌ Недостатньо коштів. Поповніть баланс.")
    update_user_balance(user_id, -data["total"])
    await callback.message.answer("✅ Замовлення прийнято! (⚠️ Надсилання на API не реалізовано)")
    await state.clear()

@dp.callback_query(F.data == "cancel_order")
async def cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("❌ Замовлення скасовано.")
    await state.clear()

# LiqPay callback
async def handle_liqpay_callback(request):
    post_data = await request.post()
    data_encoded = post_data.get("data")
    signature = post_data.get("signature")
    if not data_encoded or not signature:
        return web.Response(text="invalid")
    computed_sign = base64.b64encode(
        hashlib.sha1((LIQPAY_PRIVATE_KEY + data_encoded + LIQPAY_PRIVATE_KEY).encode()).digest()
    ).decode()
    if signature != computed_sign:
        return web.Response(text="bad signature")
    data = json.loads(base64.b64decode(data_encoded).decode())
    order_id = data.get("order_id")
    status = data.get("status")
    if status == "success" and order_id in orders:
        user_id = orders[order_id]["user_id"]
        amount = float(orders[order_id]["amount"])
        update_user_balance(user_id, amount)
        await bot.send_message(user_id, f"✅ Оплата {amount} грн зарахована на ваш баланс!")
    return web.Response(text="OK")

# Webhook запуск
async def on_startup(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook set: {WEBHOOK_URL}")

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    logging.info("Webhook deleted")

def create_app():
    app = web.Application()
    app.router.add_post("/liqpay-callback", handle_liqpay_callback)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    setup_application(app, dp, bot=bot)
    return app

if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8080)