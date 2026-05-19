import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from bybit_client import BybitClient
from strategy import analyze
from trade_tracker import TradeTracker
from telegram_bot import send_signal, send_status, send_trade_hit
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, CHECK_INTERVAL_SECONDS, SYMBOL

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

bybit   = BybitClient()
tracker = TradeTracker()


# ── Core scan logic ────────────────────────────────────────────────────────────

async def run_scan(bot, chat_id: str):
    try:
        logger.info("Running market scan…")
        data  = analyze(bybit)
        price = data["current_price"]

        # 1. Check active trade levels first
        trade = tracker.get(SYMBOL)
        if trade:
            events = tracker.check(SYMBOL, price)
            for event in events:
                await send_trade_hit(bot, chat_id, trade, event, SYMBOL, price)
                if event == "TP1":
                    tracker.mark_tp1(SYMBOL)
                else:                       # TP2 or SL — trade is over
                    tracker.close(SYMBOL)
                    trade = None
                    break

        # 2. Look for a new signal (skip if trade still active)
        if not data["signal"]:
            logger.info(
                "No signal | RSI=%.1f | F&G=%s | buy=%.1f | sell=%.1f",
                data["rsi"], data["fg_value"], data["buy_score"], data["sell_score"],
            )
            return

        if tracker.has_active(SYMBOL):
            logger.info("Signal %s ignored — trade already active", data["signal"])
            return

        logger.info("Signal: %s | score=%.1f", data["signal"], data["score"])
        await send_signal(bot, chat_id, data)
        tracker.open(
            symbol      = SYMBOL,
            signal      = data["signal"],
            limit_price = data["limit_price"],
            tp1         = data["tp1"],
            tp2         = data["tp2"],
            sl          = data["sl"],
        )

    except Exception as exc:
        logger.error("Scan error: %s", exc, exc_info=True)


# ── Command handlers ───────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *Capitex BTC Bot* is live\\!\n\n"
        "Strategy: Funding Rate \\+ Volume Spike \\+ Fear & Greed \\+ RSI\n\n"
        "*Commands:*\n"
        "/status — Market snapshot \\+ active trade\n"
        "/scan   — Force an immediate scan\n"
        "/close  — Manually close active trade\n"
        "/help   — Show this menu\n"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching market data…")
    try:
        data  = analyze(bybit)
        trade = tracker.get(SYMBOL)
        await send_status(context.bot, update.effective_chat.id, data, trade)
    except Exception as exc:
        await update.message.reply_text(f"❌ Error: `{exc}`", parse_mode="Markdown")


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Scanning market…")
    await run_scan(context.bot, update.effective_chat.id)


async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if tracker.has_active(SYMBOL):
        tracker.close(SYMBOL)
        await update.message.reply_text("✅ Active trade closed manually.")
    else:
        await update.message.reply_text("📭 No active trade to close.")


# ── Scheduled job ──────────────────────────────────────────────────────────────

async def scheduled_scan(context: ContextTypes.DEFAULT_TYPE):
    await run_scan(context.bot, TELEGRAM_CHAT_ID)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env")
    if not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_CHANNEL_ID is not set in .env")

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("scan",   cmd_scan))
    app.add_handler(CommandHandler("close",  cmd_close))

    app.job_queue.run_repeating(
        scheduled_scan,
        interval=CHECK_INTERVAL_SECONDS,
        first=15,
    )

    logger.info("Bot started | interval=%ds | public API only", CHECK_INTERVAL_SECONDS)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
