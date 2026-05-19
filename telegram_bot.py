import logging
from telegram import Bot

logger = logging.getLogger(__name__)


def _score_bar(score: float, max_score: float = 3.5) -> str:
    filled = round(score / max_score * 5)
    return "█" * filled + "░" * (5 - filled)


def _pct(a: float, b: float) -> str:
    return f"{(a / b - 1) * 100:+.2f}%"


# ── Signal message ─────────────────────────────────────────────────────────────

def build_signal_message(data: dict) -> str:
    sig    = data["signal"]
    emoji  = "🟢" if sig == "BUY" else "🔴"
    arrow  = "📈" if sig == "BUY" else "📉"
    entry  = data["limit_price"]
    reasons_text = "\n".join(f"  • {r}" for r in data["reasons"])
    bar    = _score_bar(data["score"])

    return (
        f"{emoji} *{sig} SIGNAL — {data['symbol']}* {arrow}\n\n"
        f"💰 Price:        `${data['current_price']:,.2f}`\n"
        f"📊 RSI (14):     `{data['rsi']:.2f}`\n"
        f"💸 Funding Rate: `{data['funding_rate'] * 100:.4f}%`\n"
        f"📦 Volume:       `{data['volume_ratio']:.2f}x avg`\n"
        f"😨 Fear & Greed: `{data['fg_value']} – {data['fg_label']}`\n\n"
        f"✅ *Reasons:*\n{reasons_text}\n\n"
        f"🎯 Score: `{data['score']:.1f}/3.5`  [{bar}]\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Limit Entry:* `${entry:,.2f}`\n"
        f"🎯 *TP1:*         `${data['tp1']:,.2f}`  `({_pct(data['tp1'], entry)})`\n"
        f"🚀 *TP2:*         `${data['tp2']:,.2f}`  `({_pct(data['tp2'], entry)})`\n"
        f"🛑 *SL:*          `${data['sl']:,.2f}`   `({_pct(data['sl'],  entry)})`"
    )


# ── Trade hit notifications ────────────────────────────────────────────────────

def build_tp1_message(trade: dict, symbol: str, price: float) -> str:
    entry = trade["limit_price"]
    pnl   = _pct(price, entry)
    return (
        f"✅ *TP1 HIT — {symbol}*\n\n"
        f"💰 Price now:  `${price:,.2f}`\n"
        f"📌 Entry:      `${entry:,.2f}`\n"
        f"🎯 TP1:        `${trade['tp1']:,.2f}`  `({pnl})`\n\n"
        f"🚀 Watching TP2 at `${trade['tp2']:,.2f}`\n"
        f"💡 Consider moving SL to breakeven `${entry:,.2f}`"
    )


def build_tp2_message(trade: dict, symbol: str, price: float) -> str:
    entry = trade["limit_price"]
    pnl   = _pct(price, entry)
    return (
        f"🚀 *TP2 HIT — {symbol}* ✨\n\n"
        f"💰 Price now:  `${price:,.2f}`\n"
        f"📌 Entry:      `${entry:,.2f}`\n"
        f"🚀 TP2:        `${trade['tp2']:,.2f}`  `({pnl})`\n\n"
        f"✅ *Trade closed in profit*"
    )


def build_sl_message(trade: dict, symbol: str, price: float) -> str:
    entry = trade["limit_price"]
    pnl   = _pct(price, entry)
    return (
        f"🛑 *SL HIT — {symbol}*\n\n"
        f"💰 Price now:  `${price:,.2f}`\n"
        f"📌 Entry:      `${entry:,.2f}`\n"
        f"🛑 SL:         `${trade['sl']:,.2f}`  `({pnl})`\n\n"
        f"❌ *Trade closed at loss*"
    )


# ── Status message ─────────────────────────────────────────────────────────────

def build_status_message(data: dict, active_trade: dict | None = None) -> str:
    buy_bar  = _score_bar(data["buy_score"])
    sell_bar = _score_bar(data["sell_score"])
    msg = (
        f"📡 *Market Status — {data['symbol']}*\n\n"
        f"💰 Price:        `${data['current_price']:,.2f}`\n"
        f"📊 RSI (14):     `{data['rsi']:.2f}`\n"
        f"💸 Funding:      `{data['funding_rate'] * 100:.4f}%`\n"
        f"📦 Volume:       `{data['volume_ratio']:.2f}x avg`\n"
        f"😨 Fear & Greed: `{data['fg_value']} – {data['fg_label']}`\n\n"
        f"🟢 Buy score:  `{data['buy_score']:.1f}/3.5` [{buy_bar}]\n"
        f"🔴 Sell score: `{data['sell_score']:.1f}/3.5` [{sell_bar}]"
    )
    if active_trade:
        entry = active_trade["limit_price"]
        sig   = active_trade["signal"]
        tp1_status = "✅" if active_trade["hit_tp1"] else "⏳"
        msg += (
            f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
            f"🔄 *Active {sig} Trade:*\n"
            f"📌 Entry: `${entry:,.2f}`\n"
            f"{tp1_status} TP1: `${active_trade['tp1']:,.2f}`\n"
            f"⏳ TP2:  `${active_trade['tp2']:,.2f}`\n"
            f"🛑 SL:   `${active_trade['sl']:,.2f}`"
        )
    else:
        msg += "\n\n⏳ No active trade."
    return msg


# ── Senders ────────────────────────────────────────────────────────────────────

async def send_signal(bot: Bot, chat_id: str, data: dict):
    await bot.send_message(chat_id=chat_id, text=build_signal_message(data), parse_mode="Markdown")


async def send_trade_hit(bot: Bot, chat_id: str, trade: dict, event: str, symbol: str, price: float):
    builders = {"TP1": build_tp1_message, "TP2": build_tp2_message, "SL": build_sl_message}
    text = builders[event](trade, symbol, price)
    await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")


async def send_status(bot: Bot, chat_id: str, data: dict, active_trade: dict | None = None):
    await bot.send_message(chat_id=chat_id, text=build_status_message(data, active_trade), parse_mode="Markdown")
