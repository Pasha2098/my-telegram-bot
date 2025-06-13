import os
import re
import datetime
import asyncio
import sys
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

# --- States for conversation ---
(ENTER_NAME, ENTER_CODE, CHOOSE_MAP, CHOOSE_MODE, CONFIRM_ROOM) = range(5)

# --- Room storage ---
rooms = {}

# --- Constants ---
MAPS = ["Skeld", "MIRA HQ", "Polus", "Airship", "Fungle", "Все карты"]
MODES = ["Классика", "Прятки", "Много ролей", "Баг", "Моды"]

MAX_LEN = 25
ROOM_LIFETIME = datetime.timedelta(hours=4)  # 4 часа

# --- Command menu keyboard ---
command_menu_kb = ReplyKeyboardMarkup([
    [KeyboardButton("/new"), KeyboardButton("/find")],
    [KeyboardButton("/delete"), KeyboardButton("/cancel")],
    [KeyboardButton("/commands")]
], resize_keyboard=True)

# --- Utility: очистка устаревших рум ---
def cleanup_rooms():
    now = datetime.datetime.utcnow()
    to_delete = [user_id for user_id, r in rooms.items() if now - r['created'] > ROOM_LIFETIME]
    for user_id in to_delete:
        del rooms[user_id]

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_rooms()
    welcome_text = (
        "👾 Привет, космонавт!\n"
        "Добро пожаловать в Among Us Codes Bot! 🚀\n\n"
        "Здесь ты можешь:\n"
        "🔹 Получать и делиться кодами для комнат\n"
        "🔹 Быстро находить активные лобби\n"
        "🔹 Играть с новыми друзьями без лишней суеты\n\n"
        "Введи команду /new чтобы создать код,\n"
        "или /find, чтобы найти комнату.\n\n"
        "🎮 Готов начать? Подозрения уже в воздухе... 😉\n\n"
        "📜 Правила:\n"
        "1. Удаляйте за собой румы\n"
        "2. Не создавайте фейковые румы\n"
        "3. Спам = бан\n"
        "4. Будьте вежливы\n\n"
        "Для списка команд нажми /commands"
    )
    await update.message.reply_text(welcome_text, reply_markup=command_menu_kb)

async def commands_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "/new — создать новую руму\n"
        "/find — найти активные румы\n"
        "/delete — удалить свою руму\n"
        "/cancel — отменить текущее действие\n"
        "/commands — показать это меню"
    )
    await update.message.reply_text(text, reply_markup=command_menu_kb)

async def new_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_rooms()
    user_id = update.effective_user.id
    if user_id in rooms:
        await update.message.reply_text(
            "😐 У вас уже есть активная рума. Сначала удалите её (/delete).",
            reply_markup=command_menu_kb
        )
        return ConversationHandler.END

    await update.message.reply_text("Введите имя хоста (до 25 символов):", reply_markup=ReplyKeyboardRemove())
    return ENTER_NAME

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) == 0:
        await update.message.reply_text("Имя не может быть пустым. Пожалуйста, введите имя хоста:")
        return ENTER_NAME
    if len(name) > MAX_LEN:
        await update.message.reply_text(f"Имя слишком длинное, максимум {MAX_LEN} символов. Попробуйте ещё раз:")
        return ENTER_NAME

    context.user_data['host'] = name
    await update.message.reply_text("Введите код румы (6 заглавных букв A-Z):")
    return ENTER_CODE

async def enter_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    if not re.fullmatch(r"[A-Z]{6}", code):
        await update.message.reply_text("❌ Код должен содержать ровно 6 заглавных букв A-Z. Попробуйте ещё раз:")
        return ENTER_CODE

    if any(r['code'] == code for r in rooms.values()):
        await update.message.reply_text("❌ Этот код уже используется. Введите другой код:")
        return ENTER_CODE

    context.user_data['code'] = code

    keyboard = [[InlineKeyboardButton(m, callback_data=m)] for m in MAPS]
    await update.message.reply_text("Выберите карту:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_MAP

async def choose_map(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if len(query.data) > MAX_LEN:
        await query.edit_message_text(f"Название карты слишком длинное. Попробуйте заново /new.")
        return ConversationHandler.END

    context.user_data['map'] = query.data

    keyboard = [[InlineKeyboardButton(m, callback_data=m)] for m in MODES]
    await query.edit_message_text("Выберите режим игры:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOOSE_MODE

async def choose_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if len(query.data) > MAX_LEN:
        await query.edit_message_text(f"Название режима слишком длинное. Попробуйте заново /new.")
        return ConversationHandler.END

    context.user_data['mode'] = query.data

    keyboard = [[InlineKeyboardButton("Создать", callback_data="create")]]
    room_info = (
        f"💬 Имя: {context.user_data['host']}\n"
        f"🔤 Код: *{context.user_data['code']}*\n"
        f"🗺 Карта: {context.user_data['map']}\n"
        f"🎮 Режим: {context.user_data['mode']}\n\n"
        "Создать руму?"
    )
    await query.edit_message_text(room_info, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_ROOM

async def confirm_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    now = datetime.datetime.utcnow()
    rooms[user_id] = {
        "host": context.user_data['host'],
        "code": context.user_data['code'],
        "map": context.user_data['map'],
        "mode": context.user_data['mode'],
        "created": now
    }

    context.application.create_task(auto_delete_room(user_id))

    reply_text = (
        f"✅ Рума создана!\n\n"
        f"🔤 *{context.user_data['code']}*  (нажмите кнопку ниже для копирования)\n"
        f"👤 {context.user_data['host']}\n"
        f"🗺 {context.user_data['map']}\n"
        f"🎮 {context.user_data['mode']}\n"
        f"⏳ Время жизни: 4 часа"
    )

    keyboard = [[
        InlineKeyboardButton(
            text=f"📋 {context.user_data['code']}",
            switch_inline_query_current_chat=context.user_data['code']
        )
    ]]

    await query.edit_message_text(reply_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

async def auto_delete_room(user_id):
    await asyncio.sleep(4 * 60 * 60)  # 4 часа
    rooms.pop(user_id, None)

async def find_rooms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_rooms()
    if not rooms:
        await update.message.reply_text("Пока нет активных рум. Создайте свою с помощью /new.", reply_markup=command_menu_kb)
        return

    for idx, r in enumerate(rooms.values(), 1):
        created_ago = datetime.datetime.utcnow() - r['created']
        remaining = ROOM_LIFETIME - created_ago
        minutes_left = int(remaining.total_seconds() // 60)

        text = (
            f"🔤 *{r['code']}*  (нажмите кнопку ниже для копирования)\n"
            f"👤 {r['host']}\n"
            f"🗺 {r['map']}\n"
            f"🎮 {r['mode']}\n"
            f"⏳ Осталось: {minutes_left} мин"
        )

        keyboard = [[
            InlineKeyboardButton(
                text=f"📋 {r['code']}",
                switch_inline_query_current_chat=r['code']
            )
        ]]

        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_room(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in rooms:
        del rooms[user_id]
        await update.message.reply_text("🗑 Ваша рума удалена.", reply_markup=command_menu_kb)
    else:
        await update.message.reply_text("❌ У вас нет активной румы.", reply_markup=command_menu_kb)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Действие отменено.", reply_markup=command_menu_kb)
    return ConversationHandler.END

def main():
    print("Python version:", sys.version)  # Вывод версии Python

    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        print("Ошибка: не задан токен бота в переменной окружения BOT_TOKEN")
        exit(1)

    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('new', new_room)],
        states={
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTER_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_code)],
            CHOOSE_MAP: [CallbackQueryHandler(choose_map, pattern="^(" + "|".join(MAPS) + ")$")],
            CHOOSE_MODE: [CallbackQueryHandler(choose_mode, pattern="^(" + "|".join(MODES) + ")$")],
            CONFIRM_ROOM: [CallbackQueryHandler(confirm_room, pattern="^create$")],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('commands', commands_list))
    application.add_handler(CommandHandler('find', find_rooms))
    application.add_handler(CommandHandler('delete', delete_room))
    application.add_handler(CommandHandler('cancel', cancel))
    application.add_handler(conv_handler)

    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()
