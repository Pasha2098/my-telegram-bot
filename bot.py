import asyncio
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters,
    CallbackQueryHandler
)

HOST, ROOM, MAP, MODE = range(4)

MAPS = ["The Skeld", "MIRA HQ", "Polus", "The Airship", "Fungle"]
MODES = ["Классика", "Прятки", "Много ролей", "Моды", "Баг"]

games = {}

COMMANDS_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/create"), KeyboardButton("/list")],
        [KeyboardButton("/delete"), KeyboardButton("/help")],
        [KeyboardButton("/cancel")]
    ],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "👋 *Добро пожаловать в бот Among Us!*\n\n"
        "Создавайте и находите руммы для игры с друзьями.\n"
        "Правила:\n"
        "- Имя хоста, карта и режим ограничены по длине\n"
        "- Код комнаты — 6 заглавных букв A-Z\n"
        "- Румма удаляется автоматически через 4 часа\n\n"
        "Используйте меню ниже для управления.\n"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=COMMANDS_MENU)

async def create_room_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите имя хоста:", reply_markup=ReplyKeyboardRemove())
    return HOST

async def get_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    host = update.message.text.strip()
    if len(host) > 25:
        await update.message.reply_text("Имя хоста не должно превышать 25 символов. Попробуйте снова:")
        return HOST
    context.user_data["host"] = host
    await update.message.reply_text("Введите код комнаты (6 заглавных букв A-Z):")
    return ROOM

async def get_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    room_code = update.message.text.strip().upper()
    if len(room_code) != 6 or not room_code.isalpha() or not room_code.isupper():
        await update.message.reply_text("❗ Код должен содержать ровно 6 заглавных букв A-Z. Попробуйте снова:")
        return ROOM
    if room_code in games:
        await update.message.reply_text("❗ Такая румма уже существует, введите другой код:")
        return ROOM
    context.user_data["room"] = room_code
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MAPS] + [[KeyboardButton("Отмена")]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Выберите карту:", reply_markup=reply_markup)
    return MAP

async def get_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if choice == "Отмена":
        return await cancel(update, context)
    if choice not in MAPS or len(choice) > 25:
        await update.message.reply_text("Пожалуйста, выберите карту из списка:")
        return MAP
    context.user_data["map"] = choice
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MODES] + [[KeyboardButton("Изменить карту"), KeyboardButton("Отмена")]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Выберите режим:", reply_markup=reply_markup)
    return MODE

async def get_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if choice == "Отмена":
        return await cancel(update, context)
    if choice == "Изменить карту":
        reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MAPS] + [[KeyboardButton("Отмена")]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Выберите новую карту:", reply_markup=reply_markup)
        return MAP
    if choice not in MODES or len(choice) > 25:
        await update.message.reply_text("Пожалуйста, выберите режим из списка:")
        return MODE

    user_data = context.user_data
    user_data["mode"] = choice
    room_code = user_data["room"]

    games[room_code] = {
        "host": user_data["host"],
        "room": room_code,
        "map": user_data["map"],
        "mode": user_data["mode"],
        "user_id": update.effective_user.id,
        "expiry_task": None
    }

    # Запускаем таймер удаления через 4 часа
    if games[room_code]["expiry_task"]:
        games[room_code]["expiry_task"].cancel()
    games[room_code]["expiry_task"] = asyncio.create_task(auto_delete_game(room_code))

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑 Удалить", callback_data=f"delete:{room_code}"),
            InlineKeyboardButton("✏️ Изменить", callback_data=f"edit:{room_code}"),
            InlineKeyboardButton("📋 Копировать код", callback_data=f"copycode:{room_code}"),
            InlineKeyboardButton("⏳ Продлить на 1 час", callback_data=f"extend:{room_code}")
        ]
    ])

    msg = (
        f"🛸 *Новая игра Among Us:*\n"
        f"👤 Хост: *{user_data['host']}*\n"
        f"🗺 Карта: *{user_data['map']}*\n"
        f"🎮 Режим: *{user_data['mode']}*\n\n"
        f"📥 Код комнаты:\n*{room_code}*\n\n"
        f"⌛ Эта комната будет удалена через 4 часа.\n\n"
        f"Приятной игры 😉"
    )

    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
    await update.message.reply_text("Используйте меню команд ниже для управления.", reply_markup=COMMANDS_MENU)
    return ConversationHandler.END

async def auto_delete_game(room_code):
    try:
        await asyncio.sleep(4 * 60 * 60)  # 4 часа
    except asyncio.CancelledError:
        return
    games.pop(room_code, None)

async def list_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not games:
        await update.message.reply_text("Нет активных комнат.", reply_markup=COMMANDS_MENU)
        return
    msg = "🎮 Активные комнаты:\n\n"
    for g in games.values():
        msg += f"👤 {g['host']} | Комната: {g['room']} | Карта: {g['map']} | Режим: {g['mode']}\n"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=COMMANDS_MENU)

async def delete_room_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not games:
        await update.message.reply_text("Нет румм для удаления.", reply_markup=COMMANDS_MENU)
        return
    buttons = [[KeyboardButton(code)] for code in games.keys()]
    buttons.append([KeyboardButton("Отмена")])
    reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Выберите код руммы для удаления:", reply_markup=reply_markup)
    return ROOM  # Переиспользуем ROOM для выбора кода на удаление

async def delete_room_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    room_code = update.message.text.strip().upper()
    if room_code == "Отмена":
        await update.message.reply_text("Отмена удаления.", reply_markup=COMMANDS_MENU)
        return ConversationHandler.END
    if room_code not in games:
        await update.message.reply_text("Такой руммы нет. Попробуйте снова или /cancel:", reply_markup=COMMANDS_MENU)
        return ROOM
    task = games[room_code].get("expiry_task")
    if task:
        task.cancel()
    games.pop(room_code)
    await update.message.reply_text(f"Румма {room_code} удалена.", reply_markup=COMMANDS_MENU)
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🆘 *Помощь и команды:*\n"
        "/create — создать новую румму\n"
        "/list — показать активные руммы\n"
        "/delete — удалить румму\n"
        "/cancel — отменить текущую операцию\n"
        "/help — помощь\n\n"
        "Используйте меню кнопок для удобства."
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=COMMANDS_MENU)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.", reply_markup=COMMANDS_MENU)
    return ConversationHandler.END

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("delete:"):
        room_code = data.split(":")[1]
        task = games.get(room_code, {}).get("expiry_task")
        if task:
            task.cancel()
        games.pop(room_code, None)
        await query.edit_message_text("Комната удалена.")
    elif data.startswith("edit:"):
        room_code = data.split(":")[1]
        if room_code not in games:
            await query.answer("Румма не найдена.", show_alert=True)
            return
        context.user_data.update(games[room_code])
        reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MAPS] + [[KeyboardButton("Отмена")]], resize_keyboard=True, one_time_keyboard=True)
        await query.message.reply_text("Выберите новую карту:", reply_markup=reply_markup)
        return MAP
    elif data.startswith("copycode:"):
        room_code = data.split(":")[1]
        await query.message.reply_text(f"{room_code}")
        await query.message.reply_text("Вот румма, скопируйте ее, хорошей игры")
    elif data.startswith("extend:"):
        room_code = data.split(":")[1]
        if room_code in games:
            task = games[room_code].get("expiry_task")
            if task:
                task.cancel()
            games[room_code]["expiry_task"] = asyncio.create_task(auto_delete_game(room_code))
            await query.message.reply_text("Румма продлена на 1 час.")
        else:
            await query.message.reply_text("Румма не найдена.")

async def main():
    import os
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("create", create_room_start)],
        states={
            HOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_host)],
            ROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_room)],
            MAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_map)],
            MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mode)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    delete_conv = ConversationHandler(
        entry_points=[CommandHandler("delete", delete_room_command)],
        states={
            ROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_room_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(delete_conv)
    app.add_handler(CommandHandler("list", list_games))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(CommandHandler("cancel", cancel))

    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
