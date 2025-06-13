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
    [["/start - создать румму", "/list - список румм"], ["/help - помощь", "/cancel - отмена"]],
    resize_keyboard=True
)

GREETING_TEXT = (
    "👋 *Добро пожаловать в бот Among Us!*\n\n"
    "🚀 Здесь вы можете создавать и искать комнаты для игры.\n\n"
    "📜 *Правила:*\n"
    "1. Используйте только заглавные буквы A-Z для кода комнаты.\n"
    "2. Уважайте других игроков.\n"
    "3. Комнаты удаляются через 5 часов.\n\n"
    "🛠 *Доступные команды:*\n"
    "/start — создать румму\n"
    "/list — показать активные комнаты\n"
    "/cancel — отменить создание\n"
    "/help — помощь\n"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(GREETING_TEXT, parse_mode="Markdown", reply_markup=COMMANDS_MENU)
    await update.message.reply_text(
        "Введите имя хоста:",
        reply_markup=ReplyKeyboardRemove()
    )
    return HOST

async def get_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    host = update.message.text.strip()
    if len(host) > 25:
        await update.message.reply_text("Имя хоста не должно превышать 25 символов. Введите снова:")
        return HOST
    context.user_data["host"] = host
    await update.message.reply_text("Теперь введите код комнаты (только заглавные буквы A-Z):")
    return ROOM

async def get_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    room_code = update.message.text.strip().upper()
    if not room_code.isalpha() or not room_code.isupper():
        await update.message.reply_text("❗ У вас неверный формат! Все буквы должны быть заглавными A-Z. Попробуйте снова:")
        return ROOM
    context.user_data["room"] = room_code
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MAPS] + [["Отмена"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Выберите карту:", reply_markup=reply_markup)
    return MAP

async def get_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if choice == "Отмена":
        return await cancel(update, context)
    if choice not in MAPS:
        await update.message.reply_text("Пожалуйста, выберите карту из списка:")
        return MAP
    context.user_data["map"] = choice
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MODES] + [["Изменить карту", "Отмена"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Выберите режим:", reply_markup=reply_markup)
    return MODE

async def get_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if choice == "Отмена":
        return await cancel(update, context)
    if choice == "Изменить карту":
        reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MAPS] + [["Отмена"]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Выберите новую карту:", reply_markup=reply_markup)
        return MAP
    if choice not in MODES:
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
        "user_id": update.effective_user.id
    }

    asyncio.create_task(auto_delete_game(room_code))

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑 Удалить", callback_data=f"delete:{room_code}"),
            InlineKeyboardButton("✏️ Изменить", callback_data=f"edit:{room_code}"),
            InlineKeyboardButton("📋 Копировать румму", callback_data=f"copy_room:{room_code}")
        ]
    ])

    msg = (
        f"🛸 *Новая игра Among Us:*\n"
        f"👤 Хост: *{user_data['host']}*\n"
        f"🗺 Карта: *{user_data['map']}*\n"
        f"🎮 Режим: *{user_data['mode']}*\n\n"
        f"📥 Код комнаты:\n*{room_code}*\n\n"
        f"⌛ Эта комната будет удалена через 5 часов.\n\n"
        f"Приятной игры 😉"
    )

    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
    return ConversationHandler.END

async def auto_delete_game(room_code):
    await asyncio.sleep(5 * 60 * 60)
    games.pop(room_code, None)

async def list_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not games:
        await update.message.reply_text("Нет активных комнат.", reply_markup=COMMANDS_MENU)
        return
    msg = "🎮 *Активные комнаты:*\n\n"
    for g in games.values():
        msg += f"👤 {g['host']} | Комната: {g['room']} | Карта: {g['map']} | Режим: {g['mode']}\n"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=COMMANDS_MENU)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(GREETING_TEXT, parse_mode="Markdown", reply_markup=COMMANDS_MENU)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Окей, отменено. Напишите /start, чтобы начать заново.", reply_markup=COMMANDS_MENU)
    return ConversationHandler.END

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("delete:"):
        room_code = data.split(":")[1]
        games.pop(room_code, None)
        await query.edit_message_text("Комната удалена.")
    elif data.startswith("edit:"):
        room_code = data.split(":")[1]
        context.user_data.update(games.get(room_code, {}))
        reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MAPS] + [["Отмена"]], resize_keyboard=True, one_time_keyboard=True)
        await query.message.reply_text("Выберите новую карту:", reply_markup=reply_markup)
        return MAP
    elif data.startswith("copy_room:"):
        room_code = data.split(":")[1]
        await query.message.reply_text(f"Вот румма, скопируйте ее, хорошей игры!\n\n{room_code}", reply_markup=COMMANDS_MENU)

def main():
    import os
    TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            HOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_host)],
            ROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_room)],
            MAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_map)],
            MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mode)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("list", list_games))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.run_polling()

if __name__ == '__main__':
    main()
