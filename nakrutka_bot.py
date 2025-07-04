import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from config import TELEGRAM_TOKEN
from liqpay_api import create_payment_url
from nakrutka_api import place_order

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("💬 Замовити накрутку"))
    await message.answer("Вітаю! Натисни, щоб зробити замовлення.👇", reply_markup=kb)

@dp.message_handler(lambda m: "замовити" in m.text.lower())
async def handle_order(message: types.Message):
    service = {'name': 'Підписники Instagram', 'id': 123}
    qty = 100
    total = 20.00

    payment_url = create_payment_url(amount=total, order_id="order123")

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("💳 Оплатити через LiqPay", url=payment_url))

    await message.answer(
        f"🔽 Ви обрали:\n*{service['name']}*\nКількість: {qty}\nЦіна: {total} грн",
        parse_mode="Markdown",
        reply_markup=kb
    )

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
