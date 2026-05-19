import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
TRADES_FILE = os.path.join(os.path.dirname(__file__), "active_trades.json")


class TradeTracker:
    """
    Persists one active trade per symbol to disk.
    Checks whether current price has reached TP1, TP2, or SL.
    """

    def __init__(self):
        self._trades: dict = {}
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(TRADES_FILE):
            try:
                with open(TRADES_FILE, encoding="utf-8") as f:
                    self._trades = json.load(f)
                logger.info("Loaded %d active trade(s) from disk", len(self._trades))
            except Exception as exc:
                logger.warning("Could not load trades file: %s", exc)
                self._trades = {}

    def _save(self):
        with open(TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(self._trades, f, indent=2)

    # ── CRUD ───────────────────────────────────────────────────────────────────

    def open(self, symbol: str, signal: str, limit_price: float,
             tp1: float, tp2: float, sl: float):
        self._trades[symbol] = {
            "signal":      signal,
            "limit_price": limit_price,
            "tp1":         tp1,
            "tp2":         tp2,
            "sl":          sl,
            "hit_tp1":     False,
            "opened_at":   datetime.now(timezone.utc).isoformat(),
        }
        self._save()
        logger.info("Trade opened: %s %s | entry=%.2f TP1=%.2f TP2=%.2f SL=%.2f",
                    signal, symbol, limit_price, tp1, tp2, sl)

    def get(self, symbol: str) -> dict | None:
        return self._trades.get(symbol)

    def mark_tp1(self, symbol: str):
        if symbol in self._trades:
            self._trades[symbol]["hit_tp1"] = True
            self._save()

    def close(self, symbol: str):
        if symbol in self._trades:
            del self._trades[symbol]
            self._save()
            logger.info("Trade closed: %s", symbol)

    def has_active(self, symbol: str) -> bool:
        return symbol in self._trades

    # ── Level check ────────────────────────────────────────────────────────────

    def check(self, symbol: str, price: float) -> list[str]:
        """
        Returns at most one event per call, in priority order: SL > TP1 > TP2.
        Caller is responsible for calling mark_tp1() or close() afterwards.
        """
        trade = self._trades.get(symbol)
        if not trade:
            return []

        sig     = trade["signal"]
        hit_tp1 = trade["hit_tp1"]

        if sig == "BUY":
            if price <= trade["sl"]:
                return ["SL"]
            if not hit_tp1 and price >= trade["tp1"]:
                return ["TP1"]
            if hit_tp1 and price >= trade["tp2"]:
                return ["TP2"]
        else:  # SELL
            if price >= trade["sl"]:
                return ["SL"]
            if not hit_tp1 and price <= trade["tp1"]:
                return ["TP1"]
            if hit_tp1 and price <= trade["tp2"]:
                return ["TP2"]

        return []
