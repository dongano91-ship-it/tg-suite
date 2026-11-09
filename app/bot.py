import os
import sqlite3
import asyncio
import logging
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

scheduler = AsyncIOScheduler()
REMINDERS_DB = os.path.join(os.path.dirname(__file__), "reminders.db")


def _db():
    conn = sqlite3.connect(REMINDERS_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS reminders ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " chat_id INTEGER, text TEXT, when_ts REAL, done INTEGER DEFAULT 0)"
    )
    conn.commit()
    return conn


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/start - эта справка\n"
        "/whoami - узнать твой chat_id\n"
        "/remind HH:MM текст - напомнить (например /remind 18:30 позвонить)\n"
        "/list - список активных напоминаний"
    )


async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твой chat_id: {update.effective_chat.id}")


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "Формат: /remind HH:MM текст\n"
            "Пример: /remind 18:30 позвонить маме"
        )
        return
    time_str = args[0]
    text = " ".join(args[1:])

    try:
        hh, mm = map(int, time_str.split(":"))
    except ValueError:
        await update.message.reply_text("Время в формате HH:MM, например 18:30")
        return

    now = datetime.datetime.now()
    when = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if when <= now:
        when += datetime.timedelta(days=1)

    conn = _db()
    cur = conn.execute(
        "INSERT INTO reminders (chat_id, text, when_ts) VALUES (?,?,?)",
        (update.effective_chat.id, text, when.timestamp()),
    )
    rid = cur.lastrowid
    conn.commit()
    conn.close()

    scheduler.add_job(send_reminder, 'date', run_date=when, args=[update.effective_chat.id, text, rid])
    await update.message.reply_text(f"Напомню {when.strftime('%d.%m %H:%M')}: {text}")


async def send_reminder(chat_id: int, text: str, rid: int):
    # Получаем бота для отправки сообщения
    app = Application.builder().token(BOT_TOKEN).build()
    bot = app.bot
    await bot.send_message(chat_id, f"⏰ Напоминание: {text}")

    conn = _db()
    conn.execute("UPDATE reminders SET done=1 WHERE id=?", (rid,))
    conn.commit()
    conn.close()


async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = _db()
    rows = conn.execute(
        "SELECT id, text, when_ts FROM reminders WHERE done=0 AND chat_id=?",
        (update.effective_chat.id,),
    ).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Активных напоминаний нет.")
        return

    lines = []
    for rid, t, ts in rows:
        time_str = datetime.datetime.fromtimestamp(ts).strftime('%d.%m %H:%M')
        lines.append(f"#{rid} — {time_str} — {t}")

    await update.message.reply_text("\n".join(lines))


async def main():
    scheduler.start()

    # Создаем приложение бота
    app = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("list", list_reminders))

    # Восстанавливаем напоминания после перезапуска
    conn = _db()
    rows = conn.execute(
        "SELECT id, chat_id, text, when_ts FROM reminders WHERE done=0"
    ).fetchall()
    conn.close()

    for rid, chat_id, text, ts in rows:
        when = datetime.datetime.fromtimestamp(ts)
        if when > datetime.datetime.now():
            scheduler.add_job(send_reminder, 'date', run_date=when, args=[chat_id, text, rid])

    log.info("Бот запущен!")

    # Запускаем бота
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Блокируем до получения сигнала о завершении
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
