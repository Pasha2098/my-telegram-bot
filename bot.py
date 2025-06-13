import asyncio
import json
import os
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

# Состояния
HOST, ROOM, MAP, MODE = range(4)

# Предустановленные значения
MAPS = ["The Skeld", "MIRA HQ", "Polus", "The Airship", "Fungle"]
MODES = ["Классика", "Прятки", "Много ролей", "Моды", "Баг"]

games = {}
GAMES_FILE = Path("games.json")

# Меню
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

# Команды
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ Этот бот помогает управлять комнатами для Among Us.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Действие отменено.", reply_markup=MAIN_MENU)
    return ConversationHandler.END

async def list_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not games:
        await update.message.reply_text("😕 Нет активных комнат.")
        return

    msg = "📋 *Активные комнаты:*\n\n"
    for code, g in games.items():
        msg += f"🔑 `{code}` — {g['host']} ({g['map']}, {g['mode']})\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# Сбор информации
async def get_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите имя хоста:", reply_markup=ReplyKeyboardRemove())
    return HOST

async def input_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["host"] = update.message.text.strip()
    await update.message.reply_text("Введите код комнаты:")
    return ROOM

async def input_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["room"] = update.message.text.strip().upper()
    await update.message.reply_text("Выберите карту:", reply_markup=MAPS_MENU)
    return MAP

async def input_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if choice == "Отмена":
        return await cancel(update, context)
    if choice not in MAPS:
        await update.message.reply_text("Пожалуйста, выберите карту из списка.")
        return MAP

    context.user_data["map"] = choice
    await update.message.reply_text("Выберите режим игры:", reply_markup=MODES_MENU)
    return MODE

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

# Обработка кнопок
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
            game = games[room_code]
            msg = (
                f"📋 *Копия комнаты:*\n"
                f"👤 Хост: *{game['host']}*\n"
                f"🗺 Карта: *{game['map']}*\n"
                f"🎮 Режим: *{game['mode']}*\n\n"
                f"🔑 Код: `{room_code}`\n\n"
                f"_Скопируйте этот код и поделитесь с друзьями!_"
            )
            await query.message.reply_text(msg, parse_mode="Markdown")

# Запуск
def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Ошибка: Не найден токен бота в переменной окружения BOT_TOKEN")
        return

    load_games()
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

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_games))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
