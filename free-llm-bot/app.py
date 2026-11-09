# Telegram Bot for FreeLLM API
# Связывается с локальным FreeLLM API сервером для генерации ответов

import os
import asyncio
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

load_dotenv()

BOT_TOKEN = os.environ.get("FREE_LLM_BOT_TOKEN", "")
FREE_LLM_API_URL = os.environ.get("FREE_LLM_API_URL", "http://localhost:8080")
ADMIN_CHAT_IDS = [int(x.strip()) for x in os.environ.get("FREE_LLM_ADMINS", "").split(",") if x.strip()]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Хранилище сессий (в памяти)
sessions = {}

MODELS = ["gpt-4o-mini", "claude-3-haiku", "llama-3"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - приветствие и выбор модели"""
    keyboard = []
    for model in MODELS:
        keyboard.append([InlineKeyboardButton(model, callback_data=f"model:{model}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🤖 *FreeLLM Bot v1.0*\n\n"
        f"Выберите модель или напишите свой запрос:\n\n"
        f"/models - список моделей\n"
        f"/clear - очистить историю диалога\n"
        f"/status - статус FreeLLM API\n"
        f"/help - справка\n\n"
        f"*Сейчас активна:* {sessions.get(str(update.effective_user.id), {}).get('model', 'gpt-4o-mini')}",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить историю диалога"""
    user_id = str(update.effective_user.id)
    if user_id in sessions:
        sessions[user_id]["messages"] = []
        await update.message.reply_text("✅ История очищена!")
    else:
        sessions[user_id] = {"messages": [], "model": "gpt-4o-mini"}
        await update.message.reply_text("✅ История очищена!")


async def models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать доступные модели"""
    msg = "*Доступные модели FreeLLM API:*\n\n"
    for i, model in enumerate(MODELS, 1):
        msg += f"{i}. `{model}`\n"
    msg += "\nВыберите модель кнопкой ниже:"

    keyboard = []
    for model in MODELS:
        keyboard.append([InlineKeyboardButton(model, callback_data=f"model:{model}")])

    await update.message.reply_text(msg, parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup(keyboard))


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить статус FreeLLM API"""
    try:
        response = requests.get(f"{FREE_LLM_API_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            await update.message.reply_text(
                f"✅ *FreeLLM API Online*\n"
                f"URL: `{FREE_LLM_API_URL}`\n"
                f"Status: {data.get('status', 'OK')}"
            )
        else:
            await update.message.reply_text(f"❌ API ответил со статусом: {response.status_code}")
    except requests.exceptions.ConnectionError:
        await update.message.reply_text(
            f"❌ *API недоступен*\n\n"
            f"Убедитесь, что FreeLLM Desktop запущен.\n"
            f"URL попытка: `{FREE_LLM_API_URL}`"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений"""
    if not update.message or not update.message.text:
        return

    # Проверяем права доступа
    chat_id = str(update.effective_chat.id)
    if admin_only(update):
        pass  # админ может всё
    elif not is_allowed_chat(chat_id):
        return

    user_id = str(update.effective_user.id)

    # Инициализируем сессию если нет
    if user_id not in sessions:
        sessions[user_id] = {"messages": [], "model": "gpt-4o-mini"}

    session = sessions[user_id]
    message_text = update.message.text

    # Добавляем в историю
    session["messages"].append({"role": "user", "content": message_text})

    await update.message.reply_text("⏳ Думаю...")

    try:
        # Отправляем запрос к FreeLLM API
        payload = {
            "model": session["model"],
            "messages": session["messages"],
            "stream": False
        }

        response = requests.post(
            f"{FREE_LLM_API_URL}/v1/chat/completions",
            json=payload,
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            assistant_message = result["choices"][0]["message"]["content"]
            session["messages"].append({"role": "assistant", "content": assistant_message})

            # Ограничиваем историю чтобы не выйти за лимиты
            if len(session["messages"]) > 20:
                session["messages"] = session["messages"][-10:]

            # Отправляем ответ (обрезаем если слишком длинный)
            if len(assistant_message) > 4000:
                assistant_message = assistant_message[:4000] + "...\n(сообщение обрезано)"

            await update.message.reply_text(assistant_message)
        else:
            error_msg = response.text[:500]
            logger.error(f"API error {response.status_code}: {error_msg}")
            await update.message.reply_text(f"❌ Ошибка API ({response.status_code}): {error_msg}")

    except Exception as e:
        logger.error(f"Exception: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:200]}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия кнопок"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = str(query.from_user.id)

    if data.startswith("model:"):
        model = data.replace("model:", "")
        if model in MODELS:
            if user_id not in sessions:
                sessions[user_id] = {"messages": [], "model": model}
            else:
                sessions[user_id]["model"] = model

            await query.edit_message_text(
                f"✅ Модель изменена на `{model}`\n\nИспользуйте /start для нового диалога",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("❌ Неизвестная модель")


def admin_only(update: Update) -> bool:
    """Проверяет, является ли пользователь админом"""
    if ADMIN_CHAT_IDS:
        return update.effective_user.id in ADMIN_CHAT_IDS
    return True


def is_allowed_chat(chat_id: str) -> bool:
    """Проверяет, разрешён ли чат"""
    if not ADMIN_CHAT_IDS:
        return True
    return int(chat_id) in ADMIN_CHAT_IDS


async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("models", models))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", lambda u, c: await u.message.reply_text(
        "/start - начало диалога\n"
        "/clear - очистить историю\n"
        "/models - выбрать модель\n"
        "/status - проверка API\n"
        "/help - справка\n\n"
        "Просто напишите сообщение для продолжения диалога."
    )))

    # ОбработчикCallbacks
    app.add_handler(CallbackQueryHandler(handle_callback, pattern=r"^model:"))

    # Обработчик обычных сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
