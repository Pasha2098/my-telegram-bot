import asyncio
import json
from pathlib import Path
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
GAMES_FILE = Path("games.json")

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("/start"), KeyboardButton("/list")],
        [KeyboardButton("/help"), KeyboardButton("/cancel")]
    ], resize_keyboard=True
)

MAPS_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton(m)] for m in MAPS] + [[KeyboardButton("Отмена")]],
    resize_keyboard=True, one_time_keyboard=True
)

MODES_MENU = ReplyKeyboardMarkup(
    [[KeyboardButton(m)] for m in MODES] + [[KeyboardButton("Изменить карту"), KeyboardButton("Отмена")]],
    resize_keyboard=True, one_time_keyboard=True
)

def save_games():
    temp = {}
    for code, g in games.items():
        temp[code] = {k: v for k, v in g.items() if k != "task"}
    with open(GAMES_FILE, "w", encoding="utf-8") as f:
        json.dump(temp, f, ensure_ascii=False, indent=2)

async def auto_delete_game(room_code):
    try:
        await asyncio.sleep(games[room_code]["duration"])
        if room_code in games:
            del games[room_code]
            save_games()
    except asyncio.CancelledError:
        pass

def load_games():
    if GAMES_FILE.exists():
        with open(GAMES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for code, g in data.items():
                g["task"] = asyncio.create_task(auto_delete_game(code))
                games[code] = g

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 *Добро пожаловать в бот Among Us!*\n\n"
        "Этот бот поможет вам создать и управлять руммами для игры.\n\n"
        "*Команды:*\n"
        "/start — создать румму\n"
        "/list — показать активные комнаты\n"
        "/help — помощь\n"
        "/cancel — отменить действие"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=MAIN_MENU)
    return ConversationHandler.END

# ... Остальные обработчики остаются такими же, за исключением добавлений save_games() и task

async def input_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if choice == "Отмена":
        return await cancel(update, context)
    if choice == "Изменить карту":
        await update.message.reply_text("Выберите новую карту:", reply_markup=MAPS_MENU)
        return MAP
    if choice not in MODES:
        await update.message.reply_text("Пожалуйста, выберите режим из списка:")
        return MODE
    if len(choice) > 25:
        await update.message.reply_text("Режим не должен превышать 25 символов. Выберите снова:")
        return MODE

    user_data = context.user_data
    user_data["mode"] = choice
    room_code = user_data["room"]

    task = asyncio.create_task(auto_delete_game(room_code))

    games[room_code] = {
        "host": user_data["host"],
        "room": room_code,
        "map": user_data["map"],
        "mode": user_data["mode"],
        "user_id": update.effective_user.id,
        "duration": 4 * 60 * 60,
        "task": task
    }
    save_games()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑 Удалить", callback_data=f"delete:{room_code}"),
            InlineKeyboardButton("✏️ Изменить", callback_data=f"edit:{room_code}"),
        ],
        [
            InlineKeyboardButton("⏳ Продлить на 1 час", callback_data=f"extend:{room_code}"),
            InlineKeyboardButton("📋 Копировать румму", callback_data=f"copy_room:{room_code}")
        ]
    ])

    msg = (
        f"🛸 *Новая игра Among Us:*\n"
        f"👤 Хост: *{user_data['host']}*\n"
        f"🗺 Карта: *{user_data['map']}*\n"
        f"🎮 Режим: *{user_data['mode']}*\n\n"
        f"📥 Код комнаты:\n*{room_code}*\n\n"
        f"⌛ Комната будет удалена через 4 часа.\n\n"
        f"Приятной игры 😉"
    )
    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
    return ConversationHandler.END

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("delete:"):
        room_code = data.split(":")[1]
        if room_code in games:
            task = games[room_code].get("task")
            if task:
                task.cancel()
            del games[room_code]
            save_games()
        await query.edit_message_text("Комната удалена.", reply_markup=MAIN_MENU)

    elif data.startswith("extend:"):
        room_code = data.split(":")[1]
        if room_code in games:
            task = games[room_code].get("task")
            if task:
                task.cancel()
            games[room_code]["duration"] += 3600
            games[room_code]["task"] = asyncio.create_task(auto_delete_game(room_code))
            save_games()
            await query.edit_message_text(f"⏳ Время комнаты *{room_code}* продлено на 1 час.", parse_mode="Markdown", reply_markup=MAIN_MENU)

    elif data.startswith("copy_room:"):
        room_code = data.split(":")[1]
        if room_code in games:
            await query.message.reply_text(f"Вот румма, скопируйте ее, хорошей игры!\n\n{room_code}")

# ... Остальной код: help_command, cancel, input_host, input_room, input_map — без изменений

def main():
    import os
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Ошибка: Не найден токен бота в переменной окружения BOT_TOKEN")
        return

    load_games()  # Загрузка перед запуском
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", get_host)],
        states={
            HOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_host)],
            ROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_room)],
            MAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_map)],
            MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_mode)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("list", list_games))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()


