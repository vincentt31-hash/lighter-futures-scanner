"""Price-action market-structure helpers for closed OHLCV candles.

This is a deterministic rule-based annotation layer, not a discretionary
institutional-order-flow feed. Pivots are only considered confirmed after
their right-side confirmation candles have closed.
"""
from __future__ import annotations

from typing import Any


def find_swings(
    candles: list[dict[str, Any]],
    left: int = 2,
    right: int = 2,
    max_points: int = 12,
) -> dict[str, list[dict[str, Any]]]:
    """Find confirmed fractal swing highs/lows."""
    highs: list[dict[str, Any]] = []
    lows: list[dict[str, Any]] = []
    if len(candles) < left + right + 1:
        return {"highs": highs, "lows": lows}

    for i in range(left, len(candles) - right):
        try:
            high = float(candles[i]["high"])
            low = float(candles[i]["low"])
            left_highs = [float(candles[j]["high"]) for j in range(i-left, i)]
            right_highs = [float(candles[j]["high"]) for j in range(i+1, i+right+1)]
            left_lows = [float(candles[j]["low"]) for j in range(i-left, i)]
            right_lows = [float(candles[j]["low"]) for j in range(i+1, i+right+1)]
        except (KeyError, TypeError, ValueError):
            continue

        if all(high > x for x in left_highs) and all(high >= x for x in right_highs):
            highs.append({"index": i, "price": high})
        if all(low < x for x in left_lows) and all(low <= x for x in right_lows):
            lows.append({"index": i, "price": low})

    return {"highs": highs[-max_points:], "lows": lows[-max_points:]}


def _structure_bias(swings: dict[str, list[dict[str, Any]]]) -> str:
    highs = swings["highs"]
    lows = swings["lows"]
    if len(highs) < 2 or len(lows) < 2:
        return "UNKNOWN"
    higher_high = highs[-1]["price"] > highs[-2]["price"]
    higher_low = lows[-1]["price"] > lows[-2]["price"]
    lower_high = highs[-1]["price"] < highs[-2]["price"]
    lower_low = lows[-1]["price"] < lows[-2]["price"]
    if higher_high and higher_low:
        return "BULLISH"
    if lower_high and lower_low:
        return "BEARISH"
    return "RANGE"


def detect_fvg(candles: list[dict[str, Any]], lookback: int = 30) -> list[dict[str, Any]]:
    """Return recent three-candle fair-value-gap zones, newest first."""
    gaps: list[dict[str, Any]] = []
    start = max(2, len(candles) - lookback)
    for i in range(start, len(candles)):
        try:
            first_high = float(candles[i - 2]["high"])
            first_low = float(candles[i - 2]["low"])
            third_high = float(candles[i]["high"])
            third_low = float(candles[i]["low"])
        except (KeyError, TypeError, ValueError):
            continue

        if third_low > first_high:
            gaps.append({
                "type": "BULLISH_FVG",
                "lower": first_high,
                "upper": third_low,
                "formed_at_index": i,
            })
        elif third_high < first_low:
            gaps.append({
                "type": "BEARISH_FVG",
                "lower": third_high,
                "upper": first_low,
                "formed_at_index": i,
            })
    return list(reversed(gaps[-5:]))


def analyze_market_structure(
    candles: list[dict[str, Any]],
    pivot_left: int = 2,
    pivot_right: int = 2,
) -> dict[str, Any]:
    """Annotate the latest closed candle with structure, sweeps, FVG, and S/R."""
    empty = {
        "bias": "UNKNOWN",
        "event": "NONE",
        "liquidity_sweep": "NONE",
        "last_swing_high": None,
        "last_swing_low": None,
        "support_levels": [],
        "resistance_levels": [],
        "fvgs": [],
        "note": "Not enough closed candles to confirm market structure",
    }
    if len(candles) < max(10, pivot_left + pivot_right + 3):
        return empty

    swings = find_swings(candles, pivot_left, pivot_right)
    highs = swings["highs"]
    lows = swings["lows"]
    bias = _structure_bias(swings)
    latest = candles[-1]

    try:
        close = float(latest["close"])
        high = float(latest["high"])
        low = float(latest["low"])
    except (KeyError, TypeError, ValueError):
        return empty

    last_high = highs[-1] if highs else None
    last_low = lows[-1] if lows else None
    event = "NONE"
    sweep = "NONE"

    if last_high and close > last_high["price"]:
        event = "BULLISH_CHOCH" if bias == "BEARISH" else "BULLISH_BOS"
    elif last_low and close < last_low["price"]:
        event = "BEARISH_CHOCH" if bias == "BULLISH" else "BEARISH_BOS"

    if last_high and high > last_high["price"] and close < last_high["price"]:
        sweep = "BUY_SIDE"
    elif last_low and low < last_low["price"] and close > last_low["price"]:
        sweep = "SELL_SIDE"

    support = [
        round(item["price"], 8)
        for item in reversed(lows[-5:])
    ]
    resistance = [
        round(item["price"], 8)
        for item in reversed(highs[-5:])
    ]

    return {
        "bias": bias,
        "event": event,
        "liquidity_sweep": sweep,
        "last_swing_high": round(last_high["price"], 8) if last_high else None,
        "last_swing_low": round(last_low["price"], 8) if last_low else None,
        "support_levels": support,
        "resistance_levels": resistance,
        "fvgs": detect_fvg(candles),
        "note": (
            "Confirmed pivots require right-side closed candles. "
            "FVG and liquidity-sweep labels are mechanical OHLCV approximations."
        ),
    }
