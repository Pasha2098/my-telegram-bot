import asyncio
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters,
    CallbackQueryHandler
)

# Этапы диалога
HOST, ROOM, MAP, MODE, EDIT_MAP, EDIT_MODE = range(6)

# Активные комнаты
games = {}

# Списки
MAPS = ["The Skeld", "MIRA HQ", "Polus", "The Airship", "Fungle"]
MODES = ["Классика", "Прятки", "Много ролей", "Моды", "Баг румма ❗"]

# Меню команд
COMMANDS_MENU = ReplyKeyboardMarkup([
    [
        KeyboardButton("🎮 Создать румму"),
        KeyboardButton("📋 Посмотреть руммы")
    ],
    [
        KeyboardButton("❓ Помощь")
    ]
], resize_keyboard=True)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Это бот для создания румм Among Us. Выбери действие:",
        reply_markup=COMMANDS_MENU
    )

# Команды меню
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🎮 Создать румму":
        await update.message.reply_text("Введите имя хоста:")
        return HOST
    elif text == "📋 Посмотреть руммы":
        await list_games(update, context)
        return ConversationHandler.END
    elif text == "❓ Помощь":
        await help_command(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text("Неизвестная команда.")
        return ConversationHandler.END

async def get_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    host = update.message.text.strip()
    if len(host) > 25:
        await update.message.reply_text("Имя хоста слишком длинное. Попробуйте снова:")
        return HOST
    context.user_data["host"] = host
    await update.message.reply_text("Введите код комнаты (только заглавные буквы A-Z):")
    return ROOM

async def get_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    room_code = update.message.text.strip().upper()
    if not room_code.isalpha() or not room_code.isupper():
        await update.message.reply_text("❗ У вас неверный формат! Все буквы должны быть заглавными A-Z")
        return ROOM
    context.user_data["room"] = room_code
    reply_markup = ReplyKeyboardMarkup(
        [[KeyboardButton(m)] for m in MAPS] + [[KeyboardButton("⬅️ Отменить")]],
        one_time_keyboard=True, resize_keyboard=True
    )
    await update.message.reply_text("Выбери карту:", reply_markup=reply_markup)
    return MAP

async def get_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == "⬅️ Отменить":
        await update.message.reply_text("Создание отменено.", reply_markup=COMMANDS_MENU)
        return ConversationHandler.END
    if choice not in MAPS:
        await update.message.reply_text("Выбери карту из списка")
        return MAP
    context.user_data["map"] = choice
    reply_markup = ReplyKeyboardMarkup(
        [[KeyboardButton(m)] for m in MODES] + [[KeyboardButton("⬅️ Отменить")]],
        one_time_keyboard=True, resize_keyboard=True
    )
    await update.message.reply_text("Выбери режим:", reply_markup=reply_markup)
    return MODE

async def get_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == "⬅️ Отменить":
        await update.message.reply_text("Создание отменено.", reply_markup=COMMANDS_MENU)
        return ConversationHandler.END
    if choice not in MODES:
        await update.message.reply_text("Выбери режим из списка")
        return MODE

    user_data = context.user_data
    room_code = user_data["room"]
    user_data["mode"] = choice

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
            InlineKeyboardButton("✏️ Изменить", callback_data=f"edit:{room_code}")
        ]
    ])

    msg = (
        f"🛸 *Новая игра Among Us:*\n"
        f"👤 Хост: *{user_data['host']}*\n"
        f"🗺 Карта: *{user_data['map']}*\n"
        f"🎮 Режим: *{user_data['mode']}*\n\n"
        f"📥 Код комнаты:\n{room_code}\n\n"
        f"⌛ Эта комната будет удалена через 5 часов.\n"
        f"\nПриятной игры 😉"
    )

    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown", reply_markup=COMMANDS_MENU)
    return ConversationHandler.END

async def auto_delete_game(room_code):
    await asyncio.sleep(5 * 60 * 60)
    games.pop(room_code, None)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Создание отменено.", reply_markup=COMMANDS_MENU)
    return ConversationHandler.END

async def list_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not games:
        await update.message.reply_text("Нет активных комнат.", reply_markup=COMMANDS_MENU)
        return

    msg = "🎮 Активные комнаты:\n\n"
    for g in games.values():
        msg += (
            f"👤 {g['host']} | Комната: {g['room']} | Карта: {g['map']} | Режим: {g['mode']}\n"
        )
    msg += "\nПриятной игры 😉"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=COMMANDS_MENU)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "ℹ️ *Что умеет бот:*\n"
        "\n- Создавать руммы Among Us\n"
        "- Выводить активные комнаты\n"
        "- Автоматически удалять комнаты через 5 часов\n"
        "\n📌 Команды:\n"
        "/start — Главное меню\n"
        "/cancel — Отмена создания\n"
        "\nПриятной игры!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=COMMANDS_MENU)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("delete:"):
        room_code = data.split(":")[1]
        if room_code in games:
            games.pop(room_code)
            await query.edit_message_text("❌ Комната удалена.")
    elif data.startswith("edit:"):
        await query.edit_message_text("✏️ Функция редактирования пока в разработке.")

if __name__ == "__main__":
    import os
    TOKEN = os.getenv("BOT_TOKEN")

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("🎮 Создать румму"), get_host)],
        states={
            HOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_host)],
            ROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_room)],
            MAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_map)],
            MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_mode)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Regex("^(📋 Посмотреть руммы|❓ Помощь)$"), menu_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("Бот запущен...")
    app.run_polling()
