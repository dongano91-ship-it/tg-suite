"""DealWatch Bot - 市场机会监控与通知系统

实时扫描目标市场机会，智能筛选后推送高确定性信号给管理员。
"""

import os
import sqlite3
import asyncio
import logging
import datetime
from typing import Optional, List, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("dealwatch")

# ============================================================
# 数据库
# ============================================================

DB_PATH = os.path.join(os.path.dirname(__file__), "dealwatch.db")


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            opportunity TEXT NOT NULL,
            reason TEXT NOT NULL,
            source TEXT,
            price REAL,
            target_price REAL,
            stop_loss REAL,
            confidence REAL,
            status TEXT DEFAULT 'pending',
            created_at REAL,
            updated_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scan_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL,
            keyword TEXT,
            found_count INTEGER,
            filtered_count INTEGER,
            alerted_count INTEGER
        )
    """)
    conn.commit()
    return conn


# ============================================================
# 模拟数据源（后续替换为真实 API）
# ============================================================

def mock_scan(keyword: str) -> List[Dict[str, Any]]:
    """模拟扫描结果——待替换为真实市场数据源"""
    return [
        {
            "symbol": f"{keyword.upper()}_A",
            "opportunity": f"{keyword} 突破关键阻力位",
            "reason": "技术面突破 + 基本面利好共振",
            "source": "mock",
            "price": 100.5,
            "target_price": 120.0,
            "stop_loss": 95.0,
            "confidence": 0.85
        },
        {
            "symbol": f"{keyword.upper()}_B",
            "opportunity": f"{keyword} 超跌反弹机会",
            "reason": "RSI 超卖 + 成交量放大",
            "source": "mock",
            "price": 50.2,
            "target_price": 65.0,
            "stop_loss": 47.0,
            "confidence": 0.72
        }
    ]


def save_deal(deal: Dict[str, Any]) -> int:
    conn = _db()
    now = datetime.datetime.now().timestamp()
    cur = conn.execute(
        """INSERT INTO deals
           (symbol, opportunity, reason, source, price, target_price,
            stop_loss, confidence, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            deal["symbol"], deal["opportunity"], deal["reason"],
            deal.get("source"), deal.get("price"),
            deal.get("target_price"), deal.get("stop_loss"),
            deal.get("confidence"), "pending", now, now
        )
    )
    conn.commit()
    return cur.lastrowid


def mark_resolved(deal_id: int, status: str):
    conn = _db()
    conn.execute(
        "UPDATE deals SET status=?, updated_at=? WHERE id=?",
        (status, datetime.datetime.now().timestamp(), deal_id)
    )
    conn.commit()


def log_scan(keyword: str, found: int, filtered: int, alerted: int):
    conn = _db()
    conn.execute(
        "INSERT INTO scan_log (ts, keyword, found_count, filtered_count, alerted_count) VALUES (?,?,?,?,?)",
        (datetime.datetime.now().timestamp(), keyword, found, filtered, alerted)
    )
    conn.commit()


# ============================================================
# 核心逻辑：扫描 → 筛选 → 推送
# ============================================================

async def run_scan(keyword: str, bot_chat_ids: List[int], ctx: ContextTypes.DEFAULT_TYPE):
    """执行一次完整扫描-筛选-推送流程"""
    raw_deals = mock_scan(keyword)
    found = len(raw_deals)

    # 过滤：只保留高置信度机会
    filtered = [d for d in raw_deals if d.get("confidence", 0) >= 0.7]
    filtered_count = len(filtered)

    alerted = 0
    for deal in filtered:
        deal_id = save_deal(deal)
        msg = (
            f"🎯 **新机会发现**\n\n"
            f"标的: `{deal['symbol']}`\n"
            f"机会: {deal['opportunity']}\n"
            f"原因: {deal['reason']}\n"
            f"现价: {deal.get('price', '-')} | "
            f"目标: {deal.get('target_price', '-')} | "
            f"止损: {deal.get('stop_loss', '-')}\n"
            f"置信度: {deal.get('confidence', '-')}\n\n"
            f"[ID:{deal_id}] 输入 `/resolve {deal_id}` 标记处理状态"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ 已关注", callback_data=f"resolve:{deal_id}:followed"),
            InlineKeyboardButton("❌ 忽略", callback_data=f"resolve:{deal_id}:ignored"),
        ]])
        for chat_id in bot_chat_ids:
            try:
                await ctx.bot.send_message(chat_id, msg, parse_mode="Markdown", reply_markup=keyboard)
                alerted += 1
            except Exception as e:
                log.error(f"推送失败 chat={chat_id}: {e}")

    log_scan(keyword, found, filtered_count, alerted)
    return {"found": found, "filtered": filtered_count, "alerted": alerted}


# ============================================================
# Telegram 命令处理器
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 DealWatch — 市场机会监控助手\n\n"
        "/scan <关键词>  — 立即扫描该关键词相关的机会\n"
        "/list          — 查看所有待处理机会\n"
        "/resolve <ID>  — 标记机会为已处理/已忽略\n"
        "/stats         — 查看扫描统计\n"
        "/help          — 显示此帮助"
    )


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("用法: /scan <关键词>")
        return
    keyword = " ".join(context.args)
    chat_id = str(update.effective_chat.id)
    bot_chat_ids = [int(x) for x in os.environ.get("BOT_CHAT_IDS", "").split(",") if x.strip()]
    if not bot_chat_ids:
        bot_chat_ids = [update.effective_chat.id]

    await update.message.reply_text(f"🔍 正在扫描 `{keyword}` ...")
    result = await run_scan(keyword, bot_chat_ids, context)
    await update.message.reply_text(
        f"✅ 扫描完成\n"
        f"发现: {result['found']} | 筛选后: {result['filtered']} | 推送: {result['alerted']}"
    )


async def list_deals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = _db()
    rows = conn.execute(
        "SELECT id, symbol, opportunity, price, confidence, status FROM deals ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("暂无机会记录")
        return
    lines = [f"{'ID':<6}{'标的':<15}{'机会':<20}{'价格':<10}{'置信':<8}{'状态'}"]
    lines.append("-" * 70)
    for r in rows:
        lines.append(f"{r[0]:<6}{r[1]:<15}{r[2][:18]:<20}{r[3]:<10.2f}{r[4]:<8.2f}{r[5]}")
    await update.message.reply_text("\n".join(lines))


async def resolve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    _, deal_id, action = data.split(":")
    deal_id = int(deal_id)
    status = "followed" if action == "followed" else "ignored"
    mark_resolved(deal_id, status)
    await update.callback_query.answer(f"已标记为{action}")
    await update.callback_query.edit_message_text(f"✅ 机会 #{deal_id} 已标记为「{action}」")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = _db()
    total = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM deals WHERE status='pending'").fetchone()[0]
    followed = conn.execute("SELECT COUNT(*) FROM deals WHERE status='followed'").fetchone()[0]
    ignored = conn.execute("SELECT COUNT(*) FROM deals WHERE status='ignored'").fetchone()[0]
    conn.close()
    await update.message.reply_text(
        f"📊 **扫描统计**\n\n"
        f"总机会数: {total}\n"
        f"待处理: {pending}\n"
        f"已关注: {followed}\n"
        f"已忽略: {ignored}"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **DealWatch 帮助**\n\n"
        "/scan <关键词>  立即扫描市场机会\n"
        "/list          查看所有待处理机会\n"
        "/resolve <ID>  标记机会状态\n"
        "/stats         查看扫描统计\n"
        "/start         重新开始\n\n"
        "在消息中点击按钮可以快速标记机会状态。"
    )


# ============================================================
# 入口
# ============================================================

async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan_command))
    app.add_handler(CommandHandler("list", list_deals))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(resolve_callback, pattern=r"^resolve:"))

    log.info("DealWatch bot starting...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
