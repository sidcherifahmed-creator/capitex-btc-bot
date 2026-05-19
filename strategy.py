import logging
import requests
import pandas as pd
import ta
from config import (
    RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    VOLUME_SPIKE_MULTIPLIER, FUNDING_RATE_THRESHOLD,
    FEAR_GREED_FEAR_LEVEL, FEAR_GREED_GREED_LEVEL,
    SIGNAL_MIN_SCORE, SYMBOL,
    LIMIT_OFFSET_PCT, TP1_PCT, TP2_PCT, SL_PCT,
)

logger = logging.getLogger(__name__)

FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"


# ── Indicator helpers ──────────────────────────────────────────────────────────

def calculate_rsi(df: pd.DataFrame) -> float:
    rsi_series = ta.momentum.RSIIndicator(df["close"], window=RSI_PERIOD).rsi()
    return float(rsi_series.iloc[-1])


def detect_volume_spike(df: pd.DataFrame) -> tuple[bool, float]:
    avg_vol = df["volume"].iloc[:-1].mean()
    cur_vol = df["volume"].iloc[-1]
    ratio = cur_vol / avg_vol if avg_vol > 0 else 0.0
    return ratio >= VOLUME_SPIKE_MULTIPLIER, round(ratio, 2)


def get_fear_greed() -> tuple[int | None, str]:
    try:
        resp = requests.get(FEAR_GREED_URL, timeout=10)
        resp.raise_for_status()
        entry = resp.json()["data"][0]
        return int(entry["value"]), entry["value_classification"]
    except Exception as exc:
        logger.warning("Fear & Greed fetch failed: %s", exc)
        return None, "N/A"


# ── Main analysis ──────────────────────────────────────────────────────────────

def analyze(bybit_client) -> dict:
    """
    Returns a dict with all indicator values and a signal ('BUY' | 'SELL' | None).
    Scoring:
        RSI oversold/overbought   → ±1.0
        Volume spike              → +0.5 (neutral – adds to whichever side is dominant)
        Fear & Greed extreme      → ±1.0
        Funding rate extreme      → ±1.0
    Max score per side: 3.5. Signal fires when score ≥ SIGNAL_MIN_SCORE (2.5).
    """
    df = bybit_client.get_klines()
    funding_rate = bybit_client.get_funding_rate()
    current_price = bybit_client.get_current_price()

    rsi = calculate_rsi(df)
    is_spike, volume_ratio = detect_volume_spike(df)
    fg_value, fg_label = get_fear_greed()

    buy_score = 0.0
    sell_score = 0.0
    buy_reasons: list[str] = []
    sell_reasons: list[str] = []

    # RSI
    if rsi <= RSI_OVERSOLD:
        buy_score += 1.0
        buy_reasons.append(f"RSI oversold ({rsi:.1f} ≤ {RSI_OVERSOLD})")
    elif rsi >= RSI_OVERBOUGHT:
        sell_score += 1.0
        sell_reasons.append(f"RSI overbought ({rsi:.1f} ≥ {RSI_OVERBOUGHT})")

    # Volume Spike – amplifies the dominant side
    if is_spike:
        buy_score += 0.5
        sell_score += 0.5
        note = f"Volume spike ({volume_ratio}x avg)"
        buy_reasons.append(note)
        sell_reasons.append(note)

    # Fear & Greed
    if fg_value is not None:
        if fg_value <= FEAR_GREED_FEAR_LEVEL:
            buy_score += 1.0
            buy_reasons.append(f"Fear & Greed: {fg_value} – {fg_label}")
        elif fg_value >= FEAR_GREED_GREED_LEVEL:
            sell_score += 1.0
            sell_reasons.append(f"Fear & Greed: {fg_value} – {fg_label}")

    # Funding Rate
    if funding_rate < -FUNDING_RATE_THRESHOLD:
        buy_score += 1.0
        buy_reasons.append(f"Negative funding ({funding_rate * 100:.4f}%)")
    elif funding_rate > FUNDING_RATE_THRESHOLD:
        sell_score += 1.0
        sell_reasons.append(f"Positive funding ({funding_rate * 100:.4f}%)")

    # Determine signal
    signal = None
    score = 0.0
    reasons: list[str] = []
    limit_price = tp1 = tp2 = sl = None

    if buy_score >= SIGNAL_MIN_SCORE and buy_score > sell_score:
        signal = "BUY"
        score = buy_score
        reasons = buy_reasons
        limit_price = round(current_price * (1 - LIMIT_OFFSET_PCT), 2)
        tp1         = round(limit_price   * (1 + TP1_PCT), 2)
        tp2         = round(limit_price   * (1 + TP2_PCT), 2)
        sl          = round(limit_price   * (1 - SL_PCT),  2)
    elif sell_score >= SIGNAL_MIN_SCORE and sell_score > buy_score:
        signal = "SELL"
        score = sell_score
        reasons = sell_reasons
        limit_price = round(current_price * (1 + LIMIT_OFFSET_PCT), 2)
        tp1         = round(limit_price   * (1 - TP1_PCT), 2)
        tp2         = round(limit_price   * (1 - TP2_PCT), 2)
        sl          = round(limit_price   * (1 + SL_PCT),  2)

    return {
        "symbol": SYMBOL,
        "current_price": current_price,
        "rsi": rsi,
        "funding_rate": funding_rate,
        "is_volume_spike": is_spike,
        "volume_ratio": volume_ratio,
        "fg_value": fg_value,
        "fg_label": fg_label,
        "buy_score": buy_score,
        "sell_score": sell_score,
        "signal": signal,
        "score": score,
        "reasons": reasons,
        "limit_price": limit_price,
        "tp1": tp1,
        "tp2": tp2,
        "sl": sl,
    }
