# Capitex BTC Bot

Telegram bot that monitors BTCUSDT on Bybit and fires BUY/SELL signals with automatic limit orders.

## Strategy

| Indicator | BUY condition | SELL condition | Score |
|-----------|--------------|----------------|-------|
| RSI (14) | ≤ 40 (oversold) | ≥ 60 (overbought) | ±1.0 |
| Volume Spike | > 2× average | > 2× average | +0.5 (both) |
| Fear & Greed | ≤ 30 (Fear) | ≥ 70 (Greed) | ±1.0 |
| Funding Rate | < −0.01% | > +0.01% | ±1.0 |

**Signal fires when score ≥ 2.5 on one side.**  
Limit order is placed at ±0.5% from market price.

## Setup

### 1. Create `.env`
```
cp .env.example .env
```
Fill in your values:
- `TELEGRAM_TOKEN` — from [@BotFather](https://t.me/BotFather)
- `TELEGRAM_CHAT_ID` — your Telegram user/chat ID (use [@userinfobot](https://t.me/userinfobot))
- `BYBIT_API_KEY` / `BYBIT_API_SECRET` — from Bybit API Management
- `BYBIT_TESTNET=true` for paper trading, `false` for live
- `ORDER_AMOUNT_USDT=10` — USDT per trade

### 2. Install dependencies
```
pip install -r requirements.txt
```

### 3. Run
```
python main.py
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome + command list |
| `/status` | Live market snapshot |
| `/scan` | Force immediate analysis |
| `/orders` | List open limit orders |
| `/cancel` | Cancel all open orders |

## Notes
- Without API keys the bot still sends signals but skips order placement.
- Default scan interval: every 15 minutes (configurable via `CHECK_INTERVAL_MINUTES`).
- Testnet is enabled by default — switch to live only after testing.
