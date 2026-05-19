import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")

# Symbol & Timeframe
SYMBOL = os.getenv("SYMBOL", "BTCUSDT")
INTERVAL = "15"  # 15-minute candles
KLINE_LIMIT = 100

# Strategy thresholds
RSI_PERIOD = 14
RSI_OVERSOLD = 40
RSI_OVERBOUGHT = 60
VOLUME_SPIKE_MULTIPLIER = 2.0
FUNDING_RATE_THRESHOLD = 0.0001   # 0.01%
FEAR_GREED_FEAR_LEVEL = 30
FEAR_GREED_GREED_LEVEL = 70
SIGNAL_MIN_SCORE = 2.5            # Minimum combined score to fire a signal

# Trade levels (% from entry price)
LIMIT_OFFSET_PCT = 0.005   # 0.5%  — limit order offset from market price
TP1_PCT          = 0.015   # 1.5%
TP2_PCT          = 0.030   # 3.0%
SL_PCT           = 0.015   # 1.5%

# Scan interval
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_MINUTES", "15")) * 60
