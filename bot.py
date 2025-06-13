import asyncio
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler, ConversationHandler, MessageHandler, filters
)

BOT_TOKEN = "BOT_TOKEN"

games = {}

# Состояния для ConversationHandler
CHOOSING, HOSTNAME, MAP, MODE = range(4)

ROOM_LIFETIME = 4 * 60 * 60  # 4 часа
EXTEND_TIME = 1 * 60 * 60    # 1 час

def generate_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase, k=length))

async def auto_delete_game(room_code, lifetime=ROOM_LIFETIME):
    try:
        await asyncio.sleep(lifetime)
    except asyncio.CancelledError:
        # Задача была отменена (продление)
        return
    games.pop(room_code, None)
    # Можно добавить уведомление в чат, если хотите

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Добро пожаловать в бот Among Us!*",
        parse_mode='Markdown',
    )
    await update.message.reply_text(
        "Для создания комнаты используйте команду /create"
    )
    return CHOOSING

async def create_room_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите имя хоста (максимум 25 символов):")
    return HOSTNAME

async def host_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) > 25:
        await update.message.reply_text("Имя слишком длинное, максимум 25 символов. Попробуйте снова:")
        return HOSTNAME
    context.user_data['host_name'] = text
    # Предлагаем выбрать карту
    keyboard = [
        [InlineKeyboardButton("Skeld", callback_data="map:Skeld")],
        [InlineKeyboardButton("Mira HQ", callback_data="map:MiraHQ")],
        [InlineKeyboardButton("Polus", callback_data="map:Polus")],
    ]
    await update.message.reply_text(
        "Выберите карту:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MAP

async def map_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    map_name = query.data.split(":")[1]
    context.user_data['map'] = map_name
    # Выбираем режим
    keyboard = [
        [InlineKeyboardButton("Classic", callback_data="mode:Classic")],
        [InlineKeyboardButton("Hide and Seek", callback_data="mode:HideAndSeek")],
        [InlineKeyboardButton("Proximity Chat", callback_data="mode:ProximityChat")],
    ]
    await query.edit_message_text(
        text=f"Выбрана карта: {map_name}\nВыберите режим игры:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MODE

async def mode_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    mode = query.data.split(":")[1]
    context.user_data['mode'] = mode

    # Генерируем уникальный код комнаты
    while True:
        code = generate_code()
        if code not in games:
            break

    # Сохраняем данные комнаты
    games[code] = {
        "host_name": context.user_data['host_name'],
        "map": context.user_data['map'],
        "mode": context.user_data['mode'],
        "user_id": update.effective_user.id,
        "expiry_task": None,
    }

    # Запускаем задачу автоудаления через 4 часа
    task = asyncio.create_task(auto_delete_game(code, ROOM_LIFETIME))
    games[code]["expiry_task"] = task

    keyboard = [
        [InlineKeyboardButton("Скопировать код", callback_data=f"copy:{code}")],
        [InlineKeyboardButton("Продлить румму на 1 час", callback_data=f"extend:{code}")],
        [InlineKeyboardButton("Удалить румму", callback_data=f"delete:{code}")],
    ]

    await query.edit_message_text(
        text=(f"Румма создана!\n"
              f"Код: {code}\n"
              f"Хост: {games[code]['host_name']}\n"
              f"Карта: {games[code]['map']}\n"
              f"Режим: {games[code]['mode']}\n\n"
              "⚠️ Румма удалится автоматически через 4 часа."),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("copy:"):
        code = data.split(":")[1]
        await query.message.reply_text(f"{code}")
        return

    if data.startswith("extend:"):
        code = data.split(":")[1]
        game = games.get(code)
        if not game:
            await query.message.reply_text("❗ Румма не найдена или уже удалена.")
            return
        if query.from_user.id != game["user_id"]:
            await query.message.reply_text("❗ Только создатель может продлевать румму.")
            return
        # Отмена текущей задачи удаления и запуск новой на 1 час
        task = game.get("expiry_task")
        if task:
            task.cancel()
        game["expiry_task"] = asyncio.create_task(auto_delete_game(code, EXTEND_TIME))
        await query.message.reply_text(f"✅ Румма {code} продлена на 1 час.")
        return

    if data.startswith("delete:"):
        code = data.split(":")[1]
        game = games.get(code)
        if not game:
            await query.message.reply_text("❗ Румма не найдена или уже удалена.")
            return
        if query.from_user.id != game["user_id"]:
            await query.message.reply_text("❗ Только создатель может удалять румму.")
            return
        task = game.get("expiry_task")
        if task:
            task.cancel()
        games.pop(code, None)
        await query.message.reply_text(f"🗑️ Румма {code} удалена.")
        return

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Удаление руммы через команду /delete <код>
    if len(context.args) != 1:
        await update.message.reply_text("Используйте: /delete <КОД_руммы>")
        return
    code = context.args[0].upper()
    game = games.get(code)
    if not game:
        await update.message.reply_text("❗ Румма не найдена или уже удалена.")
        return
    if update.effective_user.id != game["user_id"]:
        await update.message.reply_text("❗ Только создатель может удалять румму.")
        return
    task = game.get("expiry_task")
    if task:
        task.cancel()
    games.pop(code, None)
    await update.message.reply_text(f"🗑️ Румма {code} удалена.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('create', create_room_command)],
        states={
            HOSTNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, host_name)],
            MAP: [CallbackQueryHandler(map_choice, pattern=r"^map:")],
            MODE: [CallbackQueryHandler(mode_choice, pattern=r"^mode:")],
        },
        fallbacks=[],
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(CommandHandler('delete', delete_command))

    app.run_polling()

if __name__ == '__main__':
    main()

