# ... (усе тіло скрипта залишено без змін)
# Нижче — виправлений рядок:
await message.answer(f"🔽 Ви обрали:\n*{service['name']}*\nКількість: {qty}\nЦіна: {total} грн", parse_mode="Markdown", reply_markup=kb)