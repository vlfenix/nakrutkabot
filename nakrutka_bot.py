import base64
import hashlib
import json
import os
import requests
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
from datetime import datetime
import logging

API_TOKEN = os.getenv('API_TOKEN')
LIQPAY_PUBLIC_KEY = os.getenv('LIQPAY_PUBLIC_KEY')
LIQPAY_PRIVATE_KEY = os.getenv('LIQPAY_PRIVATE_KEY')

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

USERS_FILE = 'users.json'
orders = {}  # Зберігання очікуваних оплат

# ==== Функції роботи з балансом ====
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

def update_user_balance(user_id, amount):
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {'balance': 0}
    users[uid]['balance'] += amount
    save_users(users)

def get_user_balance(user_id):
    users = load_users()
    return users.get(str(user_id), {}).get('balance', 0)

# ==== Створення платіжного посилання ====
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
        "server_url": "https://yourdomain.com/liqpay-callback"  # Замінити на твій домен
    }
    data_str = base64.b64encode(json.dumps(data).encode()).decode()
    sign_str = LIQPAY_PRIVATE_KEY + data_str + LIQPAY_PRIVATE_KEY
    signature = base64.b64encode(hashlib.sha1(sign_str.encode()).digest()).decode()
    return f"https://www.liqpay.ua/api/3/checkout?data={data_str}&signature={signature}", order_id, amount

# ==== Telegram-хендлери ====
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("/balance", "/popovnyty")
    await message.answer("👋 Привіт! Обери команду:", reply_markup=kb)

@dp.message_handler(commands=['balance'])
async def balance_cmd(message: types.Message):
    bal = get_user_balance(message.from_user.id)
    await message.answer(f"💳 Ваш баланс: {bal} грн")

@dp.message_handler(commands=['popovnyty'])
async def popovnyty_cmd(message: types.Message):
    kb = InlineKeyboardMarkup()
    for amt in [50, 100, 200]:
        url, order_id, amount = create_payment_link(amt, message.from_user.id)
        orders[order_id] = {"user_id": message.from_user.id, "amount": amount}
        kb.add(InlineKeyboardButton(f"💸 Поповнити на {amt} грн", url=url))
    await message.answer("Оберіть суму поповнення:", reply_markup=kb)

# ==== Обробка callback від LiqPay ====
async def handle_liqpay_callback(request):
    post_data = await request.post()
    data_encoded = post_data.get("data")
    signature = post_data.get("signature")
    if not data_encoded or not signature:
        return web.Response(text="invalid")

    # Перевірка підпису
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

# ==== Запуск webhook-сервера ====
def start_webhook():
    app = web.Application()
    app.router.add_post("/liqpay-callback", handle_liqpay_callback)
    web.run_app(app, port=8080)

# ==== Старт бота ====
if __name__ == '__main__':
    import threading
    threading.Thread(target=start_webhook).start()
    executor.start_polling(dp, skip_updates=True)
