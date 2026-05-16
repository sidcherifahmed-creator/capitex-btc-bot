import os
import requests
import pandas as pd
import ta
from dotenv import load_dotenv
import schedule
import time
from datetime import datetime

load_dotenv()

TWELVE_API_KEY = os.getenv("TWELVE_DATA_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, json=payload)

def get_btc_data():
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": "BTC/USD",
        "interval": "5min",
        "outputsize": 100,
        "apikey": TWELVE_API_KEY
    }
    r = requests.get(url, params=params)
    data = r.json()
    if "values" not in data:
        print("خطأ:", data)
        return None
    df = pd.DataFrame(data["values"])
    for col in ["open","high","low","close"]:
        df[col] = pd.to_numeric(df[col])
    df = df.iloc[::-1].reset_index(drop=True)
    return df

def analyze(df):
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["ema50"] = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
    df["ema20"] = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator()
    return df

def check_signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last["close"]
    rsi = last["rsi"]
    macd = last["macd"]
    macd_sig = last["macd_signal"]
    ema50 = last["ema50"]
    ema20 = last["ema20"]

    buy = (
        price > ema50 and
        ema20 > ema50 and
        45 <= rsi <= 65 and
        macd > macd_sig and
        prev["macd"] <= prev["macd_signal"]
    )

    sell = (
        price < ema50 and
        ema20 < ema50 and
        35 <= rsi <= 55 and
        macd < macd_sig and
        prev["macd"] >= prev["macd_signal"]
    )

    return "BUY" if buy else "SELL" if sell else None

def run():
    print(f"[{datetime.now()}] جاري التحليل...")
    df = get_btc_data()
    if df is None:
        return

    df = analyze(df)
    signal = check_signal(df)

    if signal:
        price = df.iloc[-1]["close"]
        rsi = round(df.iloc[-1]["rsi"], 2)

        if signal == "BUY":
            sl = round(price - 60, 2)
            tp1 = round(price + 80, 2)
            tp2 = round(price + 150, 2)
            emoji = "🟢"
            action = "شراء"
        else:
            sl = round(price + 60, 2)
            tp1 = round(price - 80, 2)
            tp2 = round(price - 150, 2)
            emoji = "🔴"
            action = "بيع"

        msg = f"""
{emoji} <b>إشارة {action} — BTC/USD</b>
━━━━━━━━━━━━━━━━━
💰 <b>الدخول:</b> ${price:,.2f}
🎯 <b>TP1:</b> ${tp1:,.2f}
🎯 <b>TP2:</b> ${tp2:,.2f}
🛑 <b>SL:</b> ${sl:,.2f}
━━━━━━━━━━━━━━━━━
📊 RSI: {rsi}
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━
⚡️ Capitex BTC Signal
"""
        send_telegram(msg)
        print(f"✅ إشارة {signal} أُرسلت!")
    else:
        print("لا توجد إشارة الآن")

schedule.every(5).minutes.do(run)
print("🚀 Capitex BTC Bot يعمل على فريم 5 دقائق...")
run()

while True:
    schedule.run_pending()
    time.sleep(30)