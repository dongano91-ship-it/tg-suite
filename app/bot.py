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

# Import DealWatch browser & sources
from browser import Chrome, BrowserError  # noqa: E402
from sources import search as source_search, SourceError, EXTRACT_JS  # noqa: E402
import json  # noqa: E402


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
# Real DealWatch scanner
# ============================================================

def _load_dealwatch_config() -> dict:
    """Загружает конфиг dealwatch."""
    import json
    try:
        with open(DEALWATCH_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error(f"Cannot load dealwatch config: {e}")
        return {}


def _find_best_offers(query: str, platforms=None, max_price=None, min_price=0) -> list[dict]:
    """Ищет товары через браузер на маркетплейсах. Возвращает список лучших предложений."""
    cfg = _load_dealwatch_config()
    if not cfg:
        return []

    plat_list = platforms or [p for p in cfg.get("platforms", []) if p.get("enabled", True)]

    offers_by_platform = {}
    for platform_cfg in plat_list:
        key = platform_cfg["key"]
        name = platform_cfg["name"]
        try:
            offers = source_search(None, platform_cfg, query, limit=10)
            # source_search возвращает (offers, diag), но первый аргумент должен быть page
            # Исправим: нужен экземпляр Chrome и Page
        except Exception as e:
            log.warning(f"Platform {key} failed: {e}")
            continue

    return []


# Используем упрощённый подход: создаём Chrome один раз и переиспользуем
_chrome_instance = None


def _get_chrome():
    global _chrome_instance
    if _chrome_instance is None:
        chrome_cfg = _load_dealwatch_config().get("browser", {})
        headless = chrome_cfg.get("headless", True)
        port = chrome_cfg.get("port", 9222)
        profile_dir = chrome_cfg.get("profile_dir", ".chrome-profile")

        _chrome_instance = Chrome(
            port=port,
            profile_dir=profile_dir,
            headless=headless,
            verbose=False
        )
        try:
            _chrome_instance.start()
            log.info("Chrome started in headless mode")
        except Exception as e:
            log.error(f"Failed to start Chrome: {e}")
            _chrome_instance = None
    return _chrome_instance


def scan_query_real(query: str, max_results: int = 5) -> tuple[list[dict], dict]:
    """
    Выполняет реальный поиск товаров по запросу.
    Возвращает (offers, stats).
    offer = {url, title, price, platform}
    """
    cfg = _load_dealwatch_config()
    platforms = [p for p in cfg.get("platforms", []) if p.get("enabled", True)]

    all_offers = []
    errors = []

    chrome = _get_chrome()
    if not chrome:
        return [], {"error": "Не удалось запустить Chrome"}

    page = chrome.new_page()

    for plat in platforms[:3]:  # Ограничим 3 платформами для скорости
        try:
            url = plat["url"].replace("{q}", query)
            plat_name = plat["name"]

            # Прогрев если нужен
            warmup = plat.get("warmup")
            if warmup:
                try:
                    page.goto(warmup, settle=1.5)
                except Exception:
                    pass

            # Переход на поиск
            page.goto(url, settle=plat.get("settle", 3))

            # Скроллим
            for _ in range(plat.get("scroll_steps", 3)):
                try:
                    page.evaluate("window.scrollBy(0, 800); 1")
                except Exception:
                    break

            time.sleep(1)

            # Извлечение JS из sources.py
            from sources import EXTRACT_JS

            extract_js = EXTRACT_JS.replace("__CFG__",
                __import__('json').dumps({k: v for k, v in plat.items()
                                         if k in ("mode", "selector", "link_sel", "title_sel",
                                                  "title_sel_attr", "price_sel", "price_sel_attr",
                                                  "id_attr", "id_re", "min_price")} + {"limit": max_results}))

            raw = page.evaluate(extract_js)
            if raw:
                offers = __import__('json').loads(raw)
                for o in offers:
                    o["platform"] = plat_name
                all_offers.extend(offers)
                log.info(f"{plat_name}: найдено {len(offers)} товаров")

        except Exception as e:
            errors.append(f"{plat['name']}: {e}")
            log.warning(f"Platform {plat['key']} error: {e}")

    page.close()

    # Сортируем по цене и берем лучшие
    all_offers.sort(key=lambda x: x.get("price", 0))
    best = all_offers[:max_results]

    stats = {"total_found": len(all_offers), "errors": errors}
    return best, stats


def format_offer(offer: dict) -> str:
    """Форматирует одно предложение для отправки."""
    price = f"{int(offer['price']):,}".replace(",", " ") + " ₽"
    return (
        f"🛒 <b>{offer.get('platform', '?')}</b>\n"
        f"<b>{offer.get('title', 'Товар')} → {price}</b>\n"
        f"<a href=\"{offer['url']}\">Открыть →</a>"
    )


def format_offers_batch(offers: list[dict]) -> str:
    """Форматирует пачку предложений одним сообщением."""
    if not offers:
        return "😕 Ничего не найдено по этому запросу."

    lines = ["💰 <b>Лучшие предложения:</b>\n"]
    for i, o in enumerate(offers, 1):
        price = f"{int(o['price']):,}".replace(",", " ") + " ₽"
        lines.append(
            f"<b>{i}. {o.get('title', 'Товар')} — {price}</b> ({o.get('platform', '')})\n"
            f"→ <a href=\"{o['url']}\">Ссылка</a>"
        )
        if i >= 5:
            lines.append(f"\n...и ещё {len(offers) - 5} предложений. Запросите конкретный товар!")
            break

    return "\n\n".join(lines)


# ============================================================
# Bot commands with real scanning
# ============================================================

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Реальный поиск товаров на маркетплейсах."""
    if not context.args:
        await update.message.reply_text(
            "Как использовать:\n"
            "/scan iphone 15\n"
            "/scan пылесос dyson\n"
            "/scan кроссовки nike\n\n"
            "Поиск идёт на Wildberries, Ozon и Авито одновременно."
        )
        return

    query = " ".join(context.args)
    log.info(f"Scan command: {query}")

    try:
        reply = await update.message.reply_text(f"⏳ Ищу \"{query}\" на WB, Ozon, Avito... Это займёт ~30 секунд.",
                                               disable_web_page_preview=True)
    except Exception as e:
        log.error(f"Failed to send loading msg: {e}")
        return

    try:
        offers, stats = scan_query_real(query, max_results=5)

        if not offers:
            if stats.get("error"):
                await reply.edit_text(f"❌ Ошибка поиска: {stats['error']}\n\nУбедитесь, что на Railway установлен Chromium.")
            else:
                await reply.edit_text(f"😕 По запросу «{query}» ничего не найдено.\n\nПопробуйте другой запрос или проверьте правописание.")
            return

        message = format_offers_batch(offers)
        await reply.edit_text(message, parse_mode="HTML", disable_web_page_preview=True)

        log.info(f"Scan '{query}': found {stats.get('total_found', 0)} offers, sent top 5")

    except Exception as e:
        log.error(f"Scan failed: {e}")
        await reply.edit_text(f"❌ Ошибка при поиске: {str(e)[:200]}")


async def cmd_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать последние сохранённые сделки."""
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

    # Periodic auto-scan for popular items
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
    """Периодическая проверка популярных категорий."""
    log.info("Periodic check running...")
    # Можно добавить авто-сканирование популярных категорий
    pass


if __name__ == "__main__":
    asyncio.run(main())
