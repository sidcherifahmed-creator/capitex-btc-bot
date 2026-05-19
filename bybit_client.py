import logging
import requests
import pandas as pd
from config import SYMBOL, INTERVAL, KLINE_LIMIT

logger = logging.getLogger(__name__)

BYBIT_BASE = "https://api.bybit.com"


class BybitClient:
    """Reads market data from Bybit public REST API — no API keys required."""

    def _get(self, path: str, params: dict) -> dict:
        url = BYBIT_BASE + path
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode", 0) != 0:
            raise RuntimeError(f"Bybit error {data['retCode']}: {data.get('retMsg')}")
        return data

    # ── Market data ────────────────────────────────────────────────────────────

    def get_klines(self, symbol: str = SYMBOL, interval: str = INTERVAL, limit: int = KLINE_LIMIT) -> pd.DataFrame:
        data = self._get("/v5/market/kline", {
            "category": "linear",
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        })
        rows = data["result"]["list"]
        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
        df = df.astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df

    def get_ticker(self, symbol: str = SYMBOL) -> dict:
        data = self._get("/v5/market/tickers", {"category": "linear", "symbol": symbol})
        return data["result"]["list"][0]

    def get_funding_rate(self, symbol: str = SYMBOL) -> float:
        ticker = self.get_ticker(symbol)
        return float(ticker.get("fundingRate", 0))

    def get_current_price(self, symbol: str = SYMBOL) -> float:
        ticker = self.get_ticker(symbol)
        return float(ticker["lastPrice"])
