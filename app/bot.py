"""Reminders Bot with Auto-DealWatch scanning."""

import os
import sqlite3
import asyncio
import logging
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

scheduler = AsyncIOScheduler()
REMINDERS_DB = os.path.join(os.path.dirname(__file__), "reminders.db")

# DealWatch keywords (auto-scanned periodically)
DEAL_KEYWORDS = ["btc", "eth", "gold", "oil"]  # key words to scan
SCAN_INTERVAL_MINUTES = 60  # scan every hour


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
        "/list - список активных напоминаний\n"
        "/dealwatch - статус авто-сканирования сделок\n"
        "/scan BTC - мгновенно просканировать ключевое слово\n"
        "\n🔥 Авто-сканирование включено каждые 60 минут!"
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


# ============================================================
# DealWatch Auto-Scan
# ============================================================

async def send_deal_alert(chat_id: str, deal_text: str):
    """Отправить уведомление о сделке."""
    app = Application.builder().token(BOT_TOKEN).build()
    bot = app.bot
    try:
        await bot.send_message(chat_id, deal_text, parse_mode="Markdown")
    except Exception as e:
        log.error(f"Failed to send deal alert: {e}")
    finally:
        await app.stop()


async def auto_scan_deals():
    """Периодическое сканирование рыночных возможностей."""
    from app.dealwatch import mock_scan, save_deal, log_scan

    chat_ids_str = os.environ.get("BOT_CHAT_IDS", "").strip()
    if not chat_ids_str:
        log.info("BOT_CHAT_IDS not set, skipping auto-scan")
        return

    bot_chat_ids = [int(x.strip()) for x in chat_ids_str.split(",") if x.strip()]
    if not bot_chat_ids:
        log.info("No valid chat IDs found")
        return

    alerted_total = 0
    for keyword in DEAL_KEYWORDS:
        raw_deals = mock_scan(keyword)
        filtered = [d for d in raw_deals if d.get("confidence", 0) >= 0.7]

        if not filtered:
            log.info(f"Auto-scan '{keyword}': no high-confidence deals")
            continue

        for deal in filtered:
            deal_id = save_deal(deal)
            msg = (
                f"🎯 **Новая возможность!**\n\n"
                f"Объект: `{deal['symbol']}`\n"
                f"Сигнал: {deal['opportunity']}\n"
                f"Причина: {deal['reason']}\n"
                f"Цена: {deal.get('price', '-')} | Целевая: {deal.get('target_price', '-')} | Стоп: {deal.get('stop_loss', '-')}\n"
                f"Уверенность: {deal.get('confidence', '-')} | ID: #{deal_id}"
            )
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Вниманию", callback_data=f"resolve:{deal_id}:followed"),
                InlineKeyboardButton("❌ Пропустить", callback_data=f"resolve:{deal_id}:ignored"),
            ]])

            for cid in bot_chat_ids:
                await send_deal_alert(str(cid), msg)
                alerted_total += 1

        log_scan(keyword, len(raw_deals), len(filtered), len(filtered))

    log.info(f"Auto-scan completed: {alerted_total} alerts sent")


async def cmd_dealwatch_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статус DealWatch."""
    count = len(DEAL_KEYWORDS)
    await update.message.reply_text(
        f"📊 **DealWatch Статус**\n\n"
        f"Ключевые слова для сканирования: {', '.join(DEAL_KEYWORDS)}\n"
        f"Интервал: каждые {SCAN_INTERVAL_MINUTES} минут\n"
        f"Статус: ✅ Активно\n\n"
        f"/scan <ключ> - запустить сканирование сейчас"
    )


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Мгновенное сканирование по ключевому слову."""
    if not context.args:
        await update.message.reply_text("Использование: /scan <ключевое_слово>")
        return

    keyword = " ".join(context.args).lower()
    await update.message.reply_text(f"⏳ Сканирую по запросу `{keyword}` ...")

    # Запускаем в фоне
    asyncio.create_task(run_manual_scan(keyword, context))


async def run_manual_scan(keyword: str, ctx: ContextTypes.DEFAULT_TYPE):
    """Выполнить сканирование и отправить уведомления."""
    from app.dealwatch import mock_scan, save_deal, log_scan

    bot_chat_ids = [int(x) for x in os.environ.get("BOT_CHAT_IDS", "").split(",") if x.strip()]
    if not bot_chat_ids:
        bot_chat_ids = [ctx.chat_id]

    raw_deals = mock_scan(keyword)
    filtered = [d for d in raw_deals if d.get("confidence", 0) >= 0.7]

    alerted = 0
    for deal in filtered:
        deal_id = save_deal(deal)
        msg = (
            f"🎯 **Новая возможность**\n\n"
            f"Объект: `{deal['symbol']}`\n"
            f"Сигнал: {deal['opportunity']}\n"
            f"Цена: {deal.get('price', '-')} | Цель: {deal.get('target_price', '-')}"
        )
        for chat_id in bot_chat_ids:
            try:
                await ctx.bot.send_message(chat_id, msg, parse_mode="Markdown")
                alerted += 1
            except Exception as e:
                log.error(f"Send failed: {e}")

    log_scan(keyword, len(raw_deals), len(filtered), alerted)

    # Обновляем сообщение
    status_msg = (
        f"✅ Скан `{keyword}` завершён!\n"
        f"Найдено: {len(raw_deals)} | Отфильтровано: {len(filtered)} | Отправлено: {alerted}"
    )
    await ctx.message.edit_text(status_msg)


async def resolve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка кнопок подтверждения/отклонения сделки."""
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split(":")
    if len(parts) == 3 and parts[0] == "resolve":
        _, deal_id, action = parts
        msg = f"✅ Сделка #{deal_id} обработана ({action})"
        await query.edit_message_text(msg)


async def main():
    scheduler.start()

    # Создаем приложение бота
    app = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("list", list_reminders))
    app.add_handler(CommandHandler("dealwatch", cmd_dealwatch_status))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CallbackQueryHandler(resolve_callback, pattern=r"^resolve:"))

    # Обработчик обычных сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                   lambda u, c: None))  # placeholder

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

    # Запускаем периодическое сканирование сделок
    chat_ids_set = os.environ.get("BOT_CHAT_IDS", "").strip()
    if chat_ids_set:
        cron_expr = f'*/{SCAN_INTERVAL_MINUTES} * * * *'  # каждые N минут
        scheduler.add_job(auto_scan_deals, 'cron', minute='*/' + str(SCAN_INTERVAL_MINUTES),
                          id='dealwatch_auto', misfire_grace_time=60)
        log.info(f"DealWatch auto-scan scheduled every {SCAN_INTERVAL_MINUTES} minutes")
    else:
        log.warning("BOT_CHAT_IDS not set - DealWatch auto-scan disabled")

    log.info("Бот запущен с DealWatch!")

    # Запускаем бота
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # Блокируем до получения сигнала о завершении
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
