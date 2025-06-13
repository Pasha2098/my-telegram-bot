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
MODES = ["Классика", "Прятки", "Много ролей", "Моды", "Баг"]

# Команды меню
COMMANDS_MENU = ReplyKeyboardMarkup([
    ["/start - Создать румму"],
    ["/list - Список румм"],
    ["/cancel - Отменить"],
    ["/help - Помощь"]
], resize_keyboard=True)

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Добро пожаловать в мир Among Us!", reply_markup=COMMANDS_MENU)
    await update.message.reply_text("Введите имя хоста:")
    return HOST

async def get_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(update.message.text) > 25:
        await update.message.reply_text("Имя хоста должно быть до 25 символов. Попробуйте снова:")
        return HOST
    context.user_data["host"] = update.message.text
    await update.message.reply_text("Введите код комнаты (только заглавные буквы A-Z):")
    return ROOM

async def get_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    room = update.message.text.upper()
    if not room.isalpha() or not room.isupper():
        await update.message.reply_text("У вас неверный формат! Все буквы должны быть написаны заглавными A-Z.")
        return ROOM
    context.user_data["room"] = room
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MAPS], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Выберите карту:", reply_markup=reply_markup)
    return MAP

async def get_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["map"] = update.message.text
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MODES], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Выберите режим игры:", reply_markup=reply_markup)
    return MODE

async def get_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    user_data["mode"] = update.message.text
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
            InlineKeyboardButton("✏️ Изменить", callback_data=f"edit:{room_code}")
        ]
    ])

    msg = (
        f"🛸 *Новая игра Among Us:*
"
        f"👤 Хост: *{user_data['host']}*
"
        f"🗺 Карта: *{user_data['map']}*
"
        f"🎮 Режим: *{user_data['mode']}*
"
        f"📥 Код комнаты:
`{room_code}`
"
        f"⌛ Комната будет удалена через 5 часов.\n\nПриятной игры 😉"
    )

    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=keyboard)
    return ConversationHandler.END

async def auto_delete_game(room_code):
    await asyncio.sleep(5 * 60 * 60)  # 5 часов
    games.pop(room_code, None)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Окей, отменено. Напишите /start, чтобы начать заново.", reply_markup=COMMANDS_MENU)
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
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=COMMANDS_MENU)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🛠 *Доступные команды:*
"
        "/start — Создать румму\n"
        "/list — Посмотреть активные руммы\n"
        "/cancel — Отменить текущий ввод\n"
        "/help — Показать это сообщение"
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=COMMANDS_MENU)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("delete:"):
        code = data.split(":")[1]
        games.pop(code, None)
        await query.edit_message_text("Комната удалена.")

    elif data.startswith("edit:"):
        code = data.split(":")[1]
        game = games.get(code)
        if game and game["user_id"] == query.from_user.id:
            context.user_data.update(game)
            await query.edit_message_text("Выберите новую карту:",
                                          reply_markup=ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MAPS], one_time_keyboard=True, resize_keyboard=True))
            return EDIT_MAP
        else:
            await query.edit_message_text("Вы не можете редактировать эту комнату.")

    return ConversationHandler.END

async def edit_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["map"] = update.message.text
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MODES], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Выберите новый режим:", reply_markup=reply_markup)
    return EDIT_MODE

async def edit_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = update.message.text
    room_code = context.user_data["room"]

    if room_code in games:
        games[room_code].update({
            "map": context.user_data["map"],
            "mode": context.user_data["mode"]
        })
        await update.message.reply_text("Комната обновлена!", reply_markup=COMMANDS_MENU)
    else:
        await update.message.reply_text("Комната не найдена.", reply_markup=COMMANDS_MENU)

    return ConversationHandler.END

if __name__ == '__main__':
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
            EDIT_MAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_map)],
            EDIT_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_mode)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_games))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("cancel", cancel))

    print("Бот запущен...")
    app.run_polling()

