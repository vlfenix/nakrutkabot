from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
import logging
import asyncio
from config import TELEGRAM_TOKEN

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("💬 Замовити накрутку"))
    await message.answer("Привіт! Натисни кнопку нижче, щоб зробити замовлення.👇", reply_markup=kb)

@dp.message_handler(lambda m: "замовити" in m.text.lower())
async def handle_order(message: types.Message):
    service = {'name': 'Підписники Telegram'}
    qty = 100
    total = 25.00

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Оплатити через LiqPay", url="https://www.liqpay.ua"))

    await message.answer(
        f"🔽 Ви обрали:\n*{service['name']}*\nКількість: {qty}\nЦіна: {total} грн",
        parse_mode="Markdown",
        reply_markup=kb
    )

if __name__ == '__main__':
    asyncio.run(dp.start_polling())
