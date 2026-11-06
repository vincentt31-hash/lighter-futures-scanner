"""Prepare lightweight-charts compatible OHLCV and indicator payloads."""
from __future__ import annotations

from typing import Any

from .indicators import atr, ema
from .market_structure import analyze_market_structure


def build_chart_payload(
    symbol: str,
    interval: str,
    raw_candles: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a compact chart payload from normalized, closed Bybit candles."""
    candles: list[dict[str, Any]] = []
    for item in raw_candles:
        if not item.get("is_closed", False):
            continue
        try:
            timestamp = int(
                __import__("datetime").datetime.fromisoformat(
                    str(item["start_time"]).replace("Z", "+00:00")
                ).timestamp()
            )
            candle = {
                "time": timestamp,
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "volume": float(item.get("volume") or 0),
            }
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if candle["low"] <= 0 or candle["high"] < candle["low"]:
            continue
        candles.append(candle)

    candles.sort(key=lambda item: item["time"])
    closes = [item["close"] for item in candles]
    highs_lows = [
        {
            "open": item["open"],
            "high": item["high"],
            "low": item["low"],
            "close": item["close"],
            "volume": item["volume"],
        }
        for item in candles
    ]

    def line(period: int) -> list[dict[str, Any]]:
        values = ema(closes, period)
        return [
            {"time": candle["time"], "value": round(values[index], 10)}
            for index, candle in enumerate(candles)
            if index >= period - 1
        ]

    atr_values = atr(highs_lows, 14)
    structure = analyze_market_structure(highs_lows)
    markers: list[dict[str, Any]] = []
    if candles and structure.get("event") not in (None, "NONE"):
        bullish = str(structure["event"]).startswith("BULLISH")
        markers.append({
            "time": candles[-1]["time"],
            "position": "belowBar" if bullish else "aboveBar",
            "color": "#16a34a" if bullish else "#dc2626",
            "shape": "arrowUp" if bullish else "arrowDown",
            "text": structure["event"].replace("_", " "),
        })
    if candles and structure.get("liquidity_sweep") not in (None, "NONE"):
        is_sell_side = structure["liquidity_sweep"] == "SELL_SIDE"
        markers.append({
            "time": candles[-1]["time"],
            "position": "belowBar" if is_sell_side else "aboveBar",
            "color": "#0ea5e9",
            "shape": "circle",
            "text": f"{structure['liquidity_sweep']} SWEEP",
        })

    fvg_zones = []
    for zone in structure.get("fvgs", []):
        index = zone.get("formed_at_index")
        if isinstance(index, int) and 0 <= index < len(candles):
            fvg_zones.append({
                **zone,
                "start_time": candles[index]["time"],
                "end_time": candles[-1]["time"],
            })

    volume = [
        {
            "time": item["time"],
            "value": item["volume"],
            "color": "#16a34a" if item["close"] >= item["open"] else "#dc2626",
        }
        for item in candles
    ]
    atr_line = [
        {"time": candle["time"], "value": round(float(value), 10)}
        for candle, value in zip(candles, atr_values)
        if value is not None
    ]

    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "count": len(candles),
        "candles": candles,
        "volume": volume,
        "indicators": {
            "ema9": line(9),
            "ema21": line(21),
            "ema20": line(20),
            "ema50": line(50),
            "atr14": atr_line,
        },
        "market_structure": structure,
        "markers": markers,
        "fvg_zones": fvg_zones,
        "support_resistance": {
            "support": structure.get("support_levels", []),
            "resistance": structure.get("resistance_levels", []),
        },
        "data_note": "Closed candles only. EMA/ATR and structure annotations are calculated from this returned candle set.",
    }
