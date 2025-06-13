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
        [KeyboardButton("/newroom"), KeyboardButton("/list")],
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
        "/newroom — создать румму\n"
        "/list — показать активные комнаты\n"
        "/help — помощь\n"
        "/cancel — отменить действие"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=MAIN_MENU)
    return ConversationHandler.END

async def get_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    for room_code, game in games.items():
        if game["user_id"] == user_id:
            await update.message.reply_text(
                f"У вас уже есть активная румма с кодом: *{room_code}*\n"
                "Чтобы создать новую, сначала удалите старую.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
    await update.message.reply_text("Введите имя хоста (ваше имя или ник):", reply_markup=ReplyKeyboardRemove())
    return HOST

async def input_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) > 25:
        await update.message.reply_text("Имя не должно превышать 25 символов. Введите имя заново:")
        return HOST
    context.user_data["host"] = text
    await update.message.reply_text("Введите код комнаты (6 заглавных букв английского алфавита):", reply_markup=ReplyKeyboardRemove())
    return ROOM

async def input_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    if len(code) != 6 or not code.isalpha() or not code.isupper():
        await update.message.reply_text("Код должен состоять из 6 заглавных букв английского алфавита. Введите код заново:")
        return ROOM
    if code in games:
        await update.message.reply_text("Эта румма уже существует. Введите другой код:")
        return ROOM
    context.user_data["room"] = code
    await update.message.reply_text("Выберите карту:", reply_markup=MAPS_MENU)
    return MAP

async def input_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if choice == "Отмена":
        return await cancel(update, context)
    if choice not in MAPS:
        await update.message.reply_text("Пожалуйста, выберите карту из списка:")
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
    if len(choice) > 25:
        await update.message.reply_text("Режим не должен превышать 25 символов. Выберите снова:")
        return MODE

    user_data = context.user_data
    user_data["mode"] = choice
    room_code = user_data["room"]

    user_id = update.effective_user.id
    for code, game in list(games.items()):
        if game["user_id"] == user_id:
            task = game.get("task")
            if task:
                task.cancel()
            del games[code]
            save_games()
            break

    task = asyncio.create_task(auto_delete_game(room_code))

    games[room_code] = {
        "host": user_data["host"],
        "room": room_code,
        "map": user_data["map"],
        "mode": user_data["mode"],
        "user_id": user_id,
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
        ]
    ])

    msg = (
        f"🛸 *Новая игра Among Us:*\n"
        f"👤 Хост: *{user_data['host']}*\n"
        f"🗺 Карта: *{user_data['map']}*\n"
        f"🎮 Режим: *{user_data['mode']}*\n\n"
        f"📥 Код комнаты: *{room_code}*\n\n"
        f"⌛ Комната будет удалена через 4 часа.\n\n"
        f"Приятной игры 😉"
    )
    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
    return ConversationHandler.END

async def list_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not games:
        await update.message.reply_text("Активных румм пока нет.")
        return

    buttons = []
    text_lines = []
    for room_code, game in games.items():
        text_line = (
            f"👤 *{game['host']}*  |  🗺 *{game['map']}*  |  🎮 *{game['mode']}*  |  "
            f"🔑 [{room_code}](copy_{room_code})"
        )
        text_lines.append(text_line)
        buttons.append([InlineKeyboardButton(room_code, callback_data=f"copy_room:{room_code}")])

    text = "*Активные руммы:*\n\n" + "\n".join(text_lines)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Действие отменено.", reply_markup=MAIN_MENU)
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *Помощь по боту Among Us*\n\n"
        "/newroom — создать румму\n"
        "/list — показать активные руммы\n"
        "/cancel — отменить текущее действие\n"
        "/help — показать это сообщение"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=MAIN_MENU)

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
            await query.edit_message_text("Комната удалена.", reply_markup=None)

    elif data.startswith("extend:"):
        room_code = data.split(":")[1]
        if room_code in games:
            task = games[room_code].get("task")
            if task:
                task.cancel()
            games[room_code]["duration"] += 3600
            games[room_code]["task"] = asyncio.create_task(auto_delete_game(room_code))
            save_games()
            await query.edit_message_text(
                f"⏳ Время комнаты *{room_code}* продлено на 1 час.",
                parse_mode="Markdown",
                reply_markup=None
            )

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

    elif data.startswith("edit:"):
        room_code = data.split(":")[1]
        if room_code not in games:
            await query.answer("Комната не найдена.", show_alert=True)
            return
        game = games[room_code]
        user_id = update.effective_user.id
        if game["user_id"] != user_id:
            await query.answer("Вы не можете редактировать чужую румму.", show_alert=True)
            return
        await query.message.reply_text("Выберите новую карту:", reply_markup=MAPS_MENU)
        context.user_data["edit_room"] = room_code
        await query.answer()
        return MAP

async def edit_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "edit_room" not in context.user_data:
        await update.message.reply_text("Нет руммы для редактирования.", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    choice = update.message.text.strip()
    if choice == "Отмена":
        await update.message.reply_text("Редактирование отменено.", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    if choice not in MAPS:
        await update.message.reply_text("Пожалуйста, выберите карту из списка:")
        return MAP

    context.user_data["new_map"] = choice
    await update.message.reply_text("Выберите новый режим игры:", reply_markup=MODES_MENU)
    return MODE

async def edit_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "edit_room" not in context.user_data:
        await update.message.reply_text("Нет руммы для редактирования.", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    choice = update.message.text.strip()
    if choice == "Отмена":
        await update.message.reply_text("Редактирование отменено.", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    if choice == "Изменить карту":
        await update.message.reply_text("Выберите карту:", reply_markup=MAPS_MENU)
        return MAP

    if choice not in MODES:
        await update.message.reply_text("Пожалуйста, выберите режим из списка:")
        return MODE

    room_code = context.user_data["edit_room"]
    if room_code not in games:
        await update.message.reply_text("Румма не найдена.", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    games[room_code]["map"] = context.user_data["new_map"]
    games[room_code]["mode"] = choice
    save_games()

    await update.message.reply_text(
        f"Румма {room_code} обновлена:\n"
        f"🗺 Карта: {games[room_code]['map']}\n"
        f"🎮 Режим: {games[room_code]['mode']}",
        reply_markup=MAIN_MENU
    )

    context.user_data.pop("edit_room", None)
    context.user_data.pop("new_map", None)
    return ConversationHandler.END

def main():
    load_games()
    application = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()

    new_room_handler = ConversationHandler(
        entry_points=[CommandHandler("newroom", get_host)],
        states={
            HOST: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_host)],
            ROOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_room)],
            MAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_map)],
            MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_mode)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    edit_room_handler = ConversationHandler(
        entry_points=[],
        states={
            MAP: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_map)],
            MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_mode)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END,
        }
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(new_room_handler)
    application.add_handler(edit_room_handler)
    application.add_handler(CommandHandler("list", list_games))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(handle_callback))

    application.run_polling()

if __name__ == "__main__":
    main()
