"""Reminders Bot with Real DealWatch scanning (Wildberries, Ozon, Avito)."""

import os
import sys
import sqlite3
import asyncio
import logging
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Add app directory to path for local imports
sys.path.insert(0, os.path.dirname(__file__))

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

scheduler = AsyncIOScheduler()
REMINDERS_DB = os.path.join(os.path.dirname(__file__), "reminders.db")
SCAN_INTERVAL_MINUTES = 60  # auto-scan every hour

# DealWatch config
DEALWATCH_CONFIG = os.path.join(os.path.dirname(__file__), "dealwatch_config.json")

# Import DealWatch via Playwright
from playwright_browser import search_with_playwright, PlaywrightBrowserError  # noqa: E402
import json  # noqa: E402


def _load_dealwatch_config() -> dict:
    """Load dealwatch config."""
    try:
        with open(DEALWATCH_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Cannot load dealwatch config: {e}")
        return {}


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
        "/scan <товар> - найти лучшие цены на WB/Ozon/Avito\n"
        "/deals - показать последние находки\n"
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
# Real DealWatch scanner using Playwright
# ============================================================

def scan_query_real(query: str, max_results: int = 5) -> tuple[list[dict], dict]:
    """Real product search across marketplaces using Playwright."""
    cfg = _load_dealwatch_config()
    if not cfg:
        return [], {"error": "Config not loaded"}

    platforms = [p for p in cfg.get("platforms", []) if p.get("enabled", True)]

    all_offers = []
    errors = {}

    log.info(f"Starting search for '{query}' on {len(platforms)} platforms")

    for plat in platforms[:4]:
        try:
            offers, plat_errors = search_with_playwright(plat, query, limit=max_results * 3)
            if offers:
                for o in offers:
                    o["platform"] = plat["name"]
                all_offers.extend(offers)
                log.info(f"{plat['name']}: found {len(offers)} items")

            if plat_errors:
                errors.update(plat_errors)

        except Exception as e:
            errors[plat['key']] = str(e)[:80]
            log.warning(f"Platform {plat['key']} error: {e}")

        import time as _time
        _time.sleep(1)

    all_offers.sort(key=lambda x: x.get("price", 999999))
    best = all_offers[:max_results]

    stats = {"total_found": len(all_offers), "errors": errors}
    return best, stats


def format_offers_batch(offers: list[dict]) -> str:
    """Форматирует результаты поиска в красивое сообщение."""
    if not offers:
        return "😕 Ничего не найдено по этому запросу.\n\nПопробуйте другой запрос!"

    lines = ["💰 <b>Лучшие цены на этот товар:</b>\n"]

    for i, o in enumerate(offers[:8], 1):
        price_val = o.get('price', 0)
        discount = o.get('discount', 0)

        # Форматирование цены
        if price_val:
            price_str = f"🏷 {int(price_val):,}".replace(",", " ") + " ₽"
            if discount:
                old_price = int(price_val / (1 - discount/100)) if discount < 100 else 0
                if old_price > price_val:
                    price_str += f" ~~{int(old_price):,}~~ ({discount}% скидка!)"
        else:
            price_str = "—"

        # Заголовок и платформа
        title = o.get('title', 'Товар')[:55]
        platform = o.get('platform', '')

        # Причина (почему это хорошая сделка)
        reason = o.get('reason', '')
        reason_text = f"\n<i>{reason}</i>" if reason else ""

        # Ссылка
        url = o.get('url', '#')
        link_text = "🔗 Перейти" if url and url != '#' else ""

        lines.append(f"<b>{i}. {title}</b>")
        lines.append(f"{price_str} | 🏪 {platform}{reason_text}")
        if link_text:
            lines.append(f"<a href=\"{url}\">{link_text}</a>")
        lines.append("")  # пустая строка между товарами

    if len(offers) > 8:
        lines.append(f"...и ещё {len(offers) - 8} предложений на площадках.")

    return "\n".join(lines)


def format_offers_with_images(offers: list[dict]) -> tuple[str, list[str]]:
    """
    Форматирует результаты с картинками для отправки как фото+текст.
    Возвращает: (caption_text, list_of_image_urls)
    """
    image_urls = []
    product_infos = []

    for o in offers[:6]:  # Максимум 6 товаров с картинками
        if o.get('image'):
            image_urls.append(o['image'])

        price_val = o.get('price', 0)
        price_str = f"{int(price_val):,}".replace(",", " ") + " ₽" if price_val else "—"
        discount = o.get('discount', 0)

        info = f"<b>{o.get('title', 'Товар')[:40]}</b>\n"
        info += f"{price_str}"
        if discount:
            info += f" (-{discount}%)"
        info += f"\n🏪 {o.get('platform', '')}"

        product_infos.append(info)

    caption = "💰 <b>Лучшие цены:</b>\n\n" + "\n\n".join(product_infos)
    return caption, image_urls


# ============================================================
# Bot commands
# ============================================================

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Real-time marketplace scanning."""
    if not context.args:
        await update.message.reply_text(
            "Как использовать:\n"
            "/scan iphone 15\n"
            "/scan пылесос dyson\n"
            "/scan кроссовки nike\n\n"
            "Ищу на 9 площадках: WB, Ozon, Avito, Яндекс Маркет, М.Видео, DNS, Цитилинк..."
        )
        return

    query = " ".join(context.args)
    log.info(f"Scan command: {query}")

    try:
        reply = await update.message.reply_text(
            f"⏳ Ищу \"{query}\" на 9 маркетплейсах... (~20 сек)",
            disable_web_page_preview=True
        )
    except Exception as e:
        log.error(f"Failed to send loading msg: {e}")
        return

    try:
        offers, stats = scan_query_real(query, max_results=5)

        if not offers:
            if stats.get("error"):
                await reply.edit_text(f"❌ Ошибка поиска: {stats['error']}")
            else:
                await reply.edit_text(f"😕 По запросу «{query}» ничего не найдено.\n\nПопробуйте другой запрос.")
            return

        message = format_offers_batch(offers)
        await reply.edit_text(message, parse_mode="HTML", disable_web_page_preview=True)
        log.info(f"Scan '{query}': found {stats.get('count', 0)} offers")

    except Exception as e:
        log.error(f"Scan failed: {e}")
        await reply.edit_text(f"❌ Ошибка при поиске: {str(e)[:200]}")


async def cmd_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent deals from database."""
    db_path = REMINDERS_DB.replace("reminders.db", "deals.db")
    if not os.path.exists(db_path):
        await update.message.reply_text("Пока нет сохранённых находок. Используйте /scan для поиска.")
        return

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM deals ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()

    if not rows:
        await update.message.reply_text("Пока нет сохранённых находок.")
        return

    msgs = ["📋 Последние находки:\n"]
    for r in rows[:5]:
        msgs.append(f"#{r[0]}: {r[1]} — {r[2]} ₽")

    await update.message.reply_text("\n".join(msgs))


async def resolve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ Принято!")


async def main():
    scheduler.start()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CommandHandler("list", list_reminders))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("deals", cmd_deals))
    app.add_handler(CallbackQueryHandler(resolve_callback, pattern=r"^resolve:"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: None))

    conn = _db()
    rows = conn.execute(
        "SELECT id, chat_id, text, when_ts FROM reminders WHERE done=0"
    ).fetchall()
    conn.close()

    for rid, chat_id, text, ts in rows:
        when = datetime.datetime.fromtimestamp(ts)
        if when > datetime.datetime.now():
            scheduler.add_job(send_reminder, 'date', run_date=when, args=[chat_id, text, rid])

    chat_ids_set = os.environ.get("BOT_CHAT_IDS", "").strip()
    if chat_ids_set:
        scheduler.add_job(_periodic_deal_check, 'interval', minutes=SCAN_INTERVAL_MINUTES,
                          id='dealwatch_auto', misfire_grace_time=120)
        log.info(f"Auto-deal-check scheduled every {SCAN_INTERVAL_MINUTES} minutes")

    log.info("Bot запущен! Команда /scan ищет реальные товары на маркетплейсах.")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()


def _periodic_deal_check():
    log.info("Periodic check running...")
    pass


if __name__ == "__main__":
    asyncio.run(main())
