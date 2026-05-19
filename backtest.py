import os
import requests
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

TWELVE_API_KEY = os.getenv("TWELVE_DATA_API_KEY")

RISK_REWARD_TP1 = 2.0
RISK_REWARD_TP2 = 3.0
PARTIAL_CLOSE_PCT = 0.5  # 50% عند TP1

# ─── جلب البيانات التاريخية ───────────────────────────────────────────────────
def get_historical_data(interval="15min", outputsize=2000):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": "BTC/USD",
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_API_KEY,
    }
    r = requests.get(url, params=params, timeout=20)
    data = r.json()
    if "values" not in data:
        print(f"Error: {data}")
        return None
    df = pd.DataFrame(data["values"])
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.iloc[::-1].reset_index(drop=True)
    print(f"البيانات: {len(df)} شمعة من {df['datetime'].iloc[0]} إلى {df['datetime'].iloc[-1]}")
    return df

# ─── نفس دوال الاستراتيجية ───────────────────────────────────────────────────
def detect_structure(df):
    highs = df["high"].values
    lows = df["low"].values
    n = len(highs)
    if n < 20:
        return "NEUTRAL"
    pivot_highs, pivot_lows = [], []
    for i in range(2, n - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
            pivot_highs.append(highs[i])
        if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
            pivot_lows.append(lows[i])
    if len(pivot_highs) >= 2 and len(pivot_lows) >= 2:
        if pivot_highs[-1] > pivot_highs[-2] and pivot_lows[-1] > pivot_lows[-2]:
            return "BULLISH"
        if pivot_highs[-1] < pivot_highs[-2] and pivot_lows[-1] < pivot_lows[-2]:
            return "BEARISH"
    return "NEUTRAL"

def detect_liquidity_sweep(df):
    n = len(df)
    if n < 10:
        return False, None
    recent = df.iloc[-10:-1]
    last = df.iloc[-1]
    prev = df.iloc[-2]
    # BULLISH sweep
    if last["low"] < recent["low"].min() and last["close"] > prev["close"]:
        return True, "BULLISH"
    # BEARISH sweep
    if last["high"] > recent["high"].max() and last["close"] < prev["close"]:
        return True, "BEARISH"
    return False, None

def find_order_block(df, direction):
    n = len(df)
    if n < 5:
        return None
    for i in range(n - 2, max(n - 20, 1), -1):
        candle = df.iloc[i]
        body = abs(candle["close"] - candle["open"])
        avg_body = df["close"].iloc[max(0, i-10):i].sub(df["open"].iloc[max(0, i-10):i]).abs().mean()
        if avg_body == 0:
            continue
        if direction == "BULLISH":
            if candle["close"] < candle["open"] and i+1 < n and df["close"].iloc[i+1] > candle["high"] and body > avg_body * 0.5:
                if df["close"].iloc[i+1:].min() > candle["low"] * 0.998:
                    return {"high": candle["high"], "low": candle["low"], "mid": (candle["high"] + candle["low"]) / 2}
        elif direction == "BEARISH":
            if candle["close"] > candle["open"] and i+1 < n and df["close"].iloc[i+1] < candle["low"] and body > avg_body * 0.5:
                if df["close"].iloc[i+1:].max() < candle["high"] * 1.002:
                    return {"high": candle["high"], "low": candle["low"], "mid": (candle["high"] + candle["low"]) / 2}
    return None

def find_fvg(df, direction):
    n = len(df)
    for i in range(n - 3, max(n - 15, 1), -1):
        c1 = df.iloc[i - 1]
        c3 = df.iloc[i + 1]
        if direction == "BULLISH" and c3["low"] > c1["high"]:
            if df["low"].iloc[i+1:].min() > c1["high"]:
                return {"top": c3["low"], "bottom": c1["high"], "mid": (c3["low"] + c1["high"]) / 2}
        elif direction == "BEARISH" and c3["high"] < c1["low"]:
            if df["high"].iloc[i+1:].max() < c1["low"]:
                return {"top": c1["low"], "bottom": c3["high"], "mid": (c1["low"] + c3["high"]) / 2}
    return None

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def detect_rsi_divergence(df, direction, lookback=14):
    closes = df["close"].values
    rsi = calc_rsi(df["close"]).values
    n = len(closes)
    if n < lookback + 5:
        return False
    rc = closes[-lookback:]
    rr = rsi[-lookback:]
    if direction == "BULLISH":
        return rc[-1] < rc[:-1].min() and rr[-1] > rr[np.argmin(rc[:-1])]
    elif direction == "BEARISH":
        return rc[-1] > rc[:-1].max() and rr[-1] < rr[np.argmax(rc[:-1])]
    return False

def in_kill_zone(dt):
    h = dt.hour
    return (7 <= h < 10) or (13 <= h < 16)

# ─── محرك الـ Backtest ────────────────────────────────────────────────────────
def run_backtest(df):
    trades = []
    last_signal_idx = -60  # فجوة 60 شمعة (15 ساعة) بين الإشارات

    print("\nجاري تحليل البيانات...\n")

    for i in range(50, len(df) - 20):
        # Kill Zone
        if not in_kill_zone(df["datetime"].iloc[i]):
            continue

        # فجوة زمنية
        if i - last_signal_idx < 4:
            continue

        window = df.iloc[i-50:i+1].reset_index(drop=True)

        structure = detect_structure(window)
        if structure == "NEUTRAL":
            continue

        sweep, sweep_dir = detect_liquidity_sweep(window)
        if not sweep or sweep_dir != structure:
            continue

        direction = structure
        ob = find_order_block(window, direction)
        fvg = find_fvg(window, direction)
        rsi_div = detect_rsi_divergence(window, direction)

        confluence = sum([ob is not None, fvg is not None, rsi_div])
        if confluence < 1:
            continue

        # حساب الدخول (Limit)
        current_price = df["close"].iloc[i]
        if direction == "BULLISH":
            sl_base = ob["low"] if ob else df["low"].iloc[i-3:i].min()
            sl = sl_base - current_price * 0.0005
            limit_price = ob["mid"] if ob else (fvg["mid"] if fvg else current_price * 0.999)
            risk = limit_price - sl
            if risk <= 0:
                continue
            tp1 = limit_price + risk * RISK_REWARD_TP1
            tp2 = limit_price + risk * RISK_REWARD_TP2
        else:
            sl_base = ob["high"] if ob else df["high"].iloc[i-3:i].max()
            sl = sl_base + current_price * 0.0005
            limit_price = ob["mid"] if ob else (fvg["mid"] if fvg else current_price * 1.001)
            risk = sl - limit_price
            if risk <= 0:
                continue
            tp1 = limit_price - risk * RISK_REWARD_TP1
            tp2 = limit_price - risk * RISK_REWARD_TP2

        if risk / limit_price < 0.0015:
            continue

        # محاكاة الصفقة في الشموع التالية
        result = "OPEN"
        tp1_hit = False
        exit_price = None
        exit_candle = i

        for j in range(i + 1, min(i + 40, len(df))):  # أقصى 40 شمعة = 10 ساعات
            high_j = df["high"].iloc[j]
            low_j  = df["low"].iloc[j]

            if direction == "BULLISH":
                if low_j <= sl:
                    result = "SL"
                    exit_price = sl
                    exit_candle = j
                    break
                if not tp1_hit and high_j >= tp1:
                    tp1_hit = True
                if tp1_hit and high_j >= tp2:
                    result = "TP2"
                    exit_price = tp2
                    exit_candle = j
                    break
                if not tp1_hit and high_j >= tp1:
                    result = "TP1"
                    exit_price = tp1
                    exit_candle = j
                    break
            else:
                if high_j >= sl:
                    result = "SL"
                    exit_price = sl
                    exit_candle = j
                    break
                if not tp1_hit and low_j <= tp1:
                    tp1_hit = True
                if tp1_hit and low_j <= tp2:
                    result = "TP2"
                    exit_price = tp2
                    exit_candle = j
                    break
                if not tp1_hit and low_j <= tp1:
                    result = "TP1"
                    exit_price = tp1
                    exit_candle = j
                    break

        if result == "OPEN":
            continue  # تجاهل الصفقات غير المغلقة

        # حساب الربح/الخسارة بالـ R
        if result == "TP2":
            r_multiple = RISK_REWARD_TP2
        elif result == "TP1":
            r_multiple = RISK_REWARD_TP1
        else:
            r_multiple = -1.0

        trades.append({
            "date":       df["datetime"].iloc[i].strftime("%Y-%m-%d %H:%M"),
            "direction":  direction,
            "entry":      round(limit_price, 2),
            "sl":         round(sl, 2),
            "tp1":        round(tp1, 2),
            "tp2":        round(tp2, 2),
            "result":     result,
            "r":          r_multiple,
            "risk_pct":   round(risk / limit_price * 100, 3),
            "confluence": confluence,
        })

        last_signal_idx = i

    return trades

# ─── تقرير النتائج ────────────────────────────────────────────────────────────
def print_report(trades):
    if not trades:
        print("لا توجد صفقات في هذه الفترة.")
        return

    df_t = pd.DataFrame(trades)
    total      = len(df_t)
    wins       = len(df_t[df_t["result"].isin(["TP1", "TP2"])])
    losses     = len(df_t[df_t["result"] == "SL"])
    win_rate   = wins / total * 100
    total_r    = df_t["r"].sum()
    avg_r      = df_t["r"].mean()

    # أسوأ سلسلة خسائر متتالية
    max_dd = 0
    cur_dd = 0
    for r in df_t["r"]:
        if r < 0:
            cur_dd += 1
            max_dd = max(max_dd, cur_dd)
        else:
            cur_dd = 0

    # Profit Factor
    gross_win  = df_t[df_t["r"] > 0]["r"].sum()
    gross_loss = abs(df_t[df_t["r"] < 0]["r"].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")

    print("=" * 50)
    print("       نتائج الـ Backtest — Capitex SMC")
    print("=" * 50)
    print(f"إجمالي الصفقات     : {total}")
    print(f"فوز                : {wins}  ({win_rate:.1f}%)")
    print(f"خسارة              : {losses}")
    print(f"TP2 مكتمل          : {len(df_t[df_t['result']=='TP2'])}")
    print(f"TP1 فقط            : {len(df_t[df_t['result']=='TP1'])}")
    print("-" * 50)
    print(f"إجمالي R           : {total_r:+.1f}R")
    print(f"متوسط R/صفقة       : {avg_r:+.2f}R")
    print(f"Profit Factor      : {pf:.2f}")
    print(f"أسوأ خسائر متتالية : {max_dd}")
    print("=" * 50)

    # آخر 10 صفقات
    print("\nآخر 10 صفقات:")
    print(f"{'التاريخ':<18} {'الاتجاه':<8} {'النتيجة':<6} {'R':<6} {'تقاطع'}")
    print("-" * 55)
    for _, row in df_t.tail(10).iterrows():
        icon = "✅" if row["result"] in ["TP1","TP2"] else "❌"
        print(f"{row['date']:<18} {row['direction']:<8} {icon}{row['result']:<5} {row['r']:+.1f}R  {row['confluence']}/3")

    # حفظ النتائج
    df_t.to_csv("backtest_results.csv", index=False)
    print(f"\nتم حفظ النتائج في: backtest_results.csv")

# ─── التشغيل ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Capitex SMC Backtest — جلب البيانات...")
    df = get_historical_data(interval="15min", outputsize=2000)
    if df is None:
        print("فشل جلب البيانات")
        exit()

    trades = run_backtest(df)
    print_report(trades)
