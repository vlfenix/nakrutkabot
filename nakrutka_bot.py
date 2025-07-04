import logging
import json
import os
import requests
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

API_TOKEN = '7899636365:AAGrwUJLOPB0xPEjObDazOV8AAOisiwxFuM'
NAKRUTKA_API_KEY = '524cd5b9317cc5ec4843456de288beba'
NAKRUTKA_API_URL = 'https://nakrutka.cc/api/'
USERS_FILE = 'users.json'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

def get_user_balance(user_id):
    users = load_users()
    return users.get(str(user_id), {}).get('balance', 0)

def update_user_balance(user_id, amount):
    users = load_users()
    user_id = str(user_id)
    if user_id not in users:
        users[user_id] = {'balance': 0}
    users[user_id]['balance'] += amount
    save_users(users)

def deduct_user_balance(user_id, amount):
    users = load_users()
    user_id = str(user_id)
    if user_id in users and users[user_id]['balance'] >= amount:
        users[user_id]['balance'] -= amount
        save_users(users)
        return True
    return False

# /start
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton('/balance'), KeyboardButton('/nakrutka'), KeyboardButton('/popovnyty'))
    await message.answer("👋 Привіт! Це бот для накрутки. Обери команду:", reply_markup=kb)

# /balance
@dp.message_handler(commands=['balance'])
async def balance_cmd(message: types.Message):
    user_balance = get_user_balance(message.from_user.id)
    await message.answer(f"💳 Ваш баланс: {user_balance} грн")

# /popovnyty
@dp.message_handler(commands=['popovnyty'])
async def popovnyty_cmd(message: types.Message):
    await message.answer("💸 Введи суму для поповнення (наприклад: 100):")
    dp.register_message_handler(handle_topup, state=None)

def handle_topup(message: types.Message):
    try:
        amount = float(message.text)
        update_user_balance(message.from_user.id, amount)
        return executor._get_current_task().get_loop().create_task(
            message.answer(f"✅ Баланс поповнено на {amount} грн.")
        )
    except ValueError:
        return executor._get_current_task().get_loop().create_task(
            message.answer("❌ Введено некоректну суму.")
        )

# /nakrutka
@dp.message_handler(commands=['nakrutka'])
async def nakrutka_cmd(message: types.Message):
    await message.answer("🔗 Введи посилання або юзернейм для накрутки:")
    dp.register_message_handler(get_link, state=None)

def get_link(message: types.Message):
    link = message.text
    service_id = 1  # Заміни на ID реального сервісу з накрутки
    quantity = 100
    price_per_100 = 10  # Вартість у грн
    user_id = message.from_user.id
    if not deduct_user_balance(user_id, price_per_100):
        return executor._get_current_task().get_loop().create_task(
            message.answer("❌ Недостатньо коштів на балансі.")
        )

    response = requests.get(NAKRUTKA_API_URL, params={
        'key': NAKRUTKA_API_KEY,
        'action': 'add',
        'service': service_id,
        'link': link,
        'quantity': quantity
    })
    data = response.json()
    order_id = data.get('order')
    if order_id:
        msg = f"✅ Замовлення прийнято. ID: {order_id}"
    else:
        msg = f"❌ Помилка: {data}"
    return executor._get_current_task().get_loop().create_task(message.answer(msg))

# /status
@dp.message_handler(commands=['status'])
async def status_cmd(message: types.Message):
    await message.answer("🔎 Введи номер замовлення для перевірки:")
    dp.register_message_handler(check_order_status, state=None)

def check_order_status(message: types.Message):
    order_id = message.text
    response = requests.get(NAKRUTKA_API_URL, params={
        'key': NAKRUTKA_API_KEY,
        'action': 'status',
        'order': order_id
    })
    data = response.json()
    status = data.get('status', 'невідомо')
    start_count = data.get('start_count', '-')
    remains = data.get('remains', '-')
    return executor._get_current_task().get_loop().create_task(
        message.answer(f"📦 Статус: {status}\nСтарт: {start_count}\nЗалишилось: {remains}")
    )

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
