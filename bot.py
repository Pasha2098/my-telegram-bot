import asyncio
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters,
    CallbackQueryHandler
)
import re

# Этапы диалога
HOST, ROOM, MAP, MODE = range(4)

# Активные комнаты
games = {}

# Списки
MAPS = ["The Skeld", "MIRA HQ", "Polus", "The Airship"]
MODES = ["Классика", "Прятки", "Много ролей", "Моды", "Баг румма ❗"]

# Регулярка для проверки кода комнаты (только заглавные латинские буквы A-Z)
ROOM_CODE_PATTERN = re.compile(r"^[A-Z]+$")

# Меню команд внизу
COMMANDS_MENU = ReplyKeyboardMarkup([
    ["Создать румму", "Список румм"],
    ["Помощь", "Отмена"]
], resize_keyboard=True)

# Клавиатура с кнопками "Назад" и "Отмена"
def back_cancel_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("⬅️ Назад"), KeyboardButton("❌ Отмена")]
    ], resize_keyboard=True, one_time_keyboard=True)

# /start с приветствием и меню
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🛸 Добро пожаловать в Among Us Helper Bot!\n\n"
        "📜 *Правила:*\n"
        "- Код комнаты должен содержать только заглавные латинские буквы (A-Z), без пробелов.\n\n"
        "Выбирайте команду из меню ниже 👇"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=COMMANDS_MENU)
    return ConversationHandler.END

# Хэндлер для выбора команд из меню
async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Создать румму":
        await update.message.reply_text("Введите имя хоста:", reply_markup=back_cancel_keyboard())
        return HOST
    elif text == "Список румм":
        return await list_games(update, context)
    elif text == "Помощь":
        return await help_command(update, context)
    elif text == "Отмена":
        return await cancel(update, context)
    else:
        await update.message.reply_text("Выберите команду из меню.")
        return ConversationHandler.END

# Отмена в любом месте
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Окей, отменено. Напишите /start, чтобы начать заново.", reply_markup=COMMANDS_MENU)
    return ConversationHandler.END

# Обработка кнопки Назад или Отмена
async def handle_back_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE, current_step):
    text = update.message.text
    if text == "❌ Отмена":
        return await cancel(update, context)
    elif text == "⬅️ Назад":
        if current_step == ROOM:
            await update.message.reply_text("Введите имя хоста:", reply_markup=back_cancel_keyboard())
            return HOST
        elif current_step == MAP:
            await update.message.reply_text("Введите код комнаты (заглавные латинские буквы A-Z):", reply_markup=back_cancel_keyboard())
            return ROOM
        elif current_step == MODE:
            reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MAPS], one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text("Выберите карту:", reply_markup=reply_markup)
            return MAP
    # Если не нажали назад или отмену, просто вернуть None
    return None

# Проверка и ввод хоста
async def get_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем кнопки назад/отмена
    result = await handle_back_cancel(update, context, HOST)
    if result is not None:
        return result

    host = update.message.text.strip()
    if len(host) == 0:
        await update.message.reply_text("Имя хоста не может быть пустым. Попробуйте снова:", reply_markup=back_cancel_keyboard())
        return HOST
    context.user_data["host"] = host
    await update.message.reply_text("Теперь введите код комнаты (заглавные латинские буквы A-Z):", reply_markup=back_cancel_keyboard())
    return ROOM

# Проверка кода комнаты с валидацией
async def get_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await handle_back_cancel(update, context, ROOM)
    if result is not None:
        return result

    room = update.message.text.strip()
    if not ROOM_CODE_PATTERN.match(room):
        await update.message.reply_text(
            "❗ У вас неверный формат!\nВсе буквы должны быть заглавными A-Z без пробелов.\n"
            "Введите код комнаты заново:", reply_markup=back_cancel_keyboard()
        )
        return ROOM
    context.user_data["room"] = room
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MAPS], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Выберите карту:", reply_markup=reply_markup)
    return MAP

# Проверка карты по списку
async def get_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await handle_back_cancel(update, context, MAP)
    if result is not None:
        return result

    map_selected = update.message.text.strip()
    if map_selected not in MAPS:
        await update.message.reply_text("Пожалуйста, выберите карту из списка.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MAPS], one_time_keyboard=True, resize_keyboard=True))
        return MAP
    context.user_data["map"] = map_selected
    reply_markup = ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MODES], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Выберите режим игры:", reply_markup=reply_markup)
    return MODE

# Выбор режима и финальное сообщение
async def get_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await handle_back_cancel(update, context, MODE)
    if result is not None:
        return result

    mode_selected = update.message.text.strip()
    if mode_selected not in MODES:
        await update.message.reply_text("Пожалуйста, выберите режим из списка.", reply_markup=ReplyKeyboardMarkup([[KeyboardButton(m)] for m in MODES], one_time_keyboard=True, resize_keyboard=True))
        return MODE
    user_data = context.user_data
    user_data["mode"] = mode_selected
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
        f"🛸 *Новая игра Among Us:*\n"
        f"👤 Хост: *{user_data['host']}*\n"
        f"🗺 Карта: *{user_data['map']}*\n"
        f"🎮 Режим: *{user_data['mode']}*\n\n"
        f"📥 Код комнаты:\n`{room_code}`\n\n"
        f"⌛ Эта комната будет удалена через 5 часов.\n\n"
        f"Когда хотите найти румму — выбирайте команду 'Список румм' в меню.\n"
        f"Приятной игры 😉"
    )

    await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
    # Показываем меню снова
    await update.message.reply_text("Выберите команду:", reply_markup=COMMANDS_MENU)
    return ConversationHandler.END

async def auto_delete_game(room_code):
    await asyncio.sleep(5 * 60 * 60)  # 5 часов
    games.pop(room_code, None)

async def list_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not games:
        await update.message.reply_text("Нет активных комнат.", reply_markup=COMMANDS_MENU)
        return ConversationHandler.END

    msg = "🎮 Активные комнаты:\n\n"
    for g in games.values():
        msg += (
            f"👤 {g['host']} | Комната: {g['room']} | Карта: {g['map']} | Режим: {g['mode']}\n"
        )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=COMMANDS_MENU)
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 *Помощь по боту:*\n\n"
        "Создать румму — начать создание новой комнаты для игры.\n"
        "Список румм — показать все активные комнаты.\n"
        "Отмена — отменить текущее действие.\n"
        "Напишите /start для возврата в главное меню."
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=COMMANDS_MENU)
    return ConversationHandler.END

# Обработчик для меню
