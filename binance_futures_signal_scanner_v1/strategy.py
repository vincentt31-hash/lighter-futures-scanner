import math
from typing import Any, Dict, List

from .indicators import ema, rsi, atr
from .strategy_profiles import get_strategy_profile

# Hard floor: all targets are at least 1:2.
MIN_RR_FLOOR = 2.0


def analyze(
    symbol: str,
    candles_trend: List[Dict[str, Any]],
    candles_entry: List[Dict[str, Any]],
    capital: float = 100.0,
    risk_percent: float = 1.0,
    max_leverage: float = 20.0,
    min_confidence: int = 0,
    min_rr: float = 2.0,
    include_latest: bool = False,
    profile: str = "day_trade",
) -> Dict[str, Any]:
    """Analyze one symbol using a named timeframe/stop-management profile.

    The strategy is signal-only. The latest candle is excluded by default to
    avoid generating signals from an unfinished candle.
    """
    symbol = str(symbol).upper().replace("/", "").replace(".P", "")
    cfg = get_strategy_profile(profile)
    profile_name = str(profile).strip().lower()
    trend_tf = cfg["trend_timeframe"]
    entry_tf = cfg["entry_timeframe"]
    trend_fast_period = cfg["trend_fast_ema"]
    trend_slow_period = cfg["trend_slow_ema"]
    entry_fast_period = cfg["entry_fast_ema"]
    entry_slow_period = cfg["entry_slow_ema"]

    indicators_out: Dict[str, Any] = {
        "ema_trend_fast": None,
        "ema_trend_slow": None,
        "ema_entry_fast": None,
        "ema_entry_slow": None,
        "rsi_entry": None,
        "atr_entry": None,
        "atr_trend": None,
        "trend": None,
        "volume_confirmed": None,
        # Legacy aliases retained for the Android client.
        "ema20_1h": None,
        "ema50_1h": None,
        "ema9_15m": None,
        "ema21_15m": None,
        "rsi_15m": None,
        "atr_15m": None,
        "atr_1h": None,
        "trend_1h": None,
    }

    def no_signal(reason: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "signal": "NO_SIGNAL",
            "status": "NO_SIGNAL",
            "reason": reason,
            "strategy_profile": profile_name,
            "timeframe_entry": entry_tf,
            "timeframe_trend": trend_tf,
            "trend": indicators_out["trend"],
            "trend_1h": indicators_out["trend"],
            "indicators": indicators_out,
        }

    if not candles_trend or not candles_entry:
        return no_signal("No candle data")
    if capital <= 0:
        return no_signal("Capital must be greater than zero")
    if risk_percent <= 0:
        return no_signal("Risk percent must be greater than zero")
    if max_leverage < 1:
        return no_signal("Leverage must be at least 1")
    if min_rr <= 0:
        return no_signal("Risk reward must be greater than zero")

    rr = max(float(min_rr), MIN_RR_FLOOR)
    ch = candles_trend if include_latest else candles_trend[:-1]
    ce = candles_entry if include_latest else candles_entry[:-1]

    if len(ch) < cfg["min_trend_candles"] or len(ce) < cfg["min_entry_candles"]:
        return no_signal("Insufficient closed candles")

    try:
        close_trend = [float(c["close"]) for c in ch]
        close_entry = [float(c["close"]) for c in ce]
        if any((not math.isfinite(p)) or p <= 0 for p in close_trend + close_entry):
            return no_signal("Invalid candle price")
    except (KeyError, TypeError, ValueError):
        return no_signal("Invalid candle format")

    trend_fast = ema(close_trend, trend_fast_period)
    trend_slow = ema(close_trend, trend_slow_period)
    atr_trend_series = atr(ch, 14)
    entry_fast = ema(close_entry, entry_fast_period)
    entry_slow = ema(close_entry, entry_slow_period)
    rsi_entry = rsi(close_entry, 14)
    atr_entry_series = atr(ce, 14)

    i = len(ce) - 1
    j = len(ch) - 1
    required = [
        trend_fast[j], trend_slow[j], atr_trend_series[j],
        entry_fast[i], entry_slow[i], rsi_entry[i], atr_entry_series[i],
    ]
    if any(value is None for value in required):
        return no_signal("Indicators not ready")

    try:
        last = ce[i]
        o = float(last["open"])
        h = float(last["high"])
        l = float(last["low"])
        entry = float(last["close"])
        volumes = [float(c.get("volume", 0) or 0) for c in ce]
    except (KeyError, TypeError, ValueError):
        return no_signal("Invalid candle format")

    atr_e = float(atr_entry_series[i])
    atr_t = float(atr_trend_series[j])
    current_rsi = float(rsi_entry[i])
    if entry <= 0 or atr_e <= 0 or atr_t <= 0:
        return no_signal("Invalid ATR or entry price")

    trend_up = trend_fast[j] > trend_slow[j] and close_trend[j] > trend_slow[j]
    trend_down = trend_fast[j] < trend_slow[j] and close_trend[j] < trend_slow[j]
    trend = "UP" if trend_up else "DOWN" if trend_down else "SIDEWAYS"

    average_volume = sum(volumes[-21:-1]) / 20 if len(volumes) >= 21 else 0
    volume_confirmed = average_volume > 0 and volumes[i] >= average_volume

    indicators_out.update({
        "ema_trend_fast": round(float(trend_fast[j]), 8),
        "ema_trend_slow": round(float(trend_slow[j]), 8),
        "ema_entry_fast": round(float(entry_fast[i]), 8),
        "ema_entry_slow": round(float(entry_slow[i]), 8),
        "rsi_entry": round(current_rsi, 4),
        "atr_entry": round(atr_e, 8),
        "atr_trend": round(atr_t, 8),
        "trend": trend,
        "volume_confirmed": volume_confirmed,
        # Keep the original field names populated for existing UI clients.
        "ema20_1h": round(float(trend_fast[j]), 8),
        "ema50_1h": round(float(trend_slow[j]), 8),
        "ema9_15m": round(float(entry_fast[i]), 8),
        "ema21_15m": round(float(entry_slow[i]), 8),
        "rsi_15m": round(current_rsi, 4),
        "atr_15m": round(atr_e, 8),
        "atr_1h": round(atr_t, 8),
        "trend_1h": trend,
    })

    if trend == "SIDEWAYS":
        return no_signal(f"{trend_tf} trend is sideways")
    if (h - l) > cfg["max_entry_range_atr"] * atr_e:
        return no_signal("Entry candle too extended")

    lookback = cfg["pullback_lookback"]
    recent = ce[i - lookback:i]
    try:
        pulled_back_long = any(
            float(c["low"]) <= entry_fast[i - lookback + k]
            for k, c in enumerate(recent)
        )
        pulled_back_short = any(
            float(c["high"]) >= entry_fast[i - lookback + k]
            for k, c in enumerate(recent)
        )
    except (KeyError, TypeError, ValueError):
        return no_signal("Invalid candle format")

    long_rsi_min, long_rsi_max = cfg["rsi_long"]
    short_rsi_min, short_rsi_max = cfg["rsi_short"]
    long_signal = (
        trend_up
        and entry_fast[i] > entry_slow[i]
        and pulled_back_long
        and entry > entry_fast[i]
        and entry > o
        and long_rsi_min <= current_rsi <= long_rsi_max
    )
    short_signal = (
        trend_down
        and entry_fast[i] < entry_slow[i]
        and pulled_back_short
        and entry < entry_fast[i]
        and entry < o
        and short_rsi_min <= current_rsi <= short_rsi_max
    )
    if not long_signal and not short_signal:
        if trend_up:
            return no_signal(
                f"{trend_tf} uptrend, waiting for {entry_tf} pullback + EMA reclaim"
            )
        return no_signal(
            f"{trend_tf} downtrend, waiting for {entry_tf} pullback + EMA rejection"
        )

    max_stop_distance = cfg["max_stop_pct"] * entry
    stop_floor = min(
        max(cfg["atr_floor_mult"] * atr_t, cfg["min_stop_pct"] * entry),
        max_stop_distance,
    )
    stop_cap = max(
        stop_floor,
        min(cfg["atr_cap_mult"] * atr_t, max_stop_distance),
    )
    swing = ch[-cfg["swing_lookback"]:]

    if long_signal:
        direction = "LONG"
        swing_low = min(float(c["low"]) for c in swing)
        raw_stop = swing_low - cfg["swing_atr_buffer"] * atr_t
        risk = min(max(entry - raw_stop, stop_floor), stop_cap)
        stop_loss = entry - risk
    else:
        direction = "SHORT"
        swing_high = max(float(c["high"]) for c in swing)
        raw_stop = swing_high + cfg["swing_atr_buffer"] * atr_t
        risk = min(max(raw_stop - entry, stop_floor), stop_cap)
        stop_loss = entry + risk

    sign = 1 if direction == "LONG" else -1
    tp1 = entry + sign * rr * risk
    tp2 = entry + sign * (rr + 1.0) * risk
    tp3 = entry + sign * (rr + 2.0) * risk
    if risk <= 0 or stop_loss <= 0 or tp1 <= 0:
        return no_signal("Invalid risk geometry")

    risk_amount = capital * (risk_percent / 100.0)
    stop_pct = risk / entry
    notional_target = risk_amount / stop_pct
    # Conservative heuristic only; actual liquidation depends on exchange
    # maintenance margin, fees, funding, position mode, and market conditions.
    safe_leverage = max(1, int(math.floor(0.8 / stop_pct)))
    effective_max_leverage = max(1.0, min(float(max_leverage), float(safe_leverage)))
    notional = min(notional_target, capital * effective_max_leverage)
    leverage_used = max(
        1,
        int(min(max(1, math.ceil(notional / capital)), effective_max_leverage)),
    )
    position_qty = notional / entry
    margin_usdt = notional / leverage_used
    estimated_loss = notional * stop_pct
    profit_tp1 = notional * stop_pct * rr
    profit_tp2 = notional * stop_pct * (rr + 1.0)

    confidence = 60
    if volume_confirmed:
        confidence += 10
    if abs(trend_fast[j] - trend_slow[j]) / close_trend[j] >= 0.003:
        confidence += 8
    bonus_long_min, bonus_long_max = cfg["rsi_bonus_long"]
    bonus_short_min, bonus_short_max = cfg["rsi_bonus_short"]
    if direction == "LONG" and bonus_long_min <= current_rsi <= bonus_long_max:
        confidence += 7
    if direction == "SHORT" and bonus_short_min <= current_rsi <= bonus_short_max:
        confidence += 7
    if (
        (direction == "LONG" and close_trend[j] > trend_fast[j])
        or (direction == "SHORT" and close_trend[j] < trend_fast[j])
    ):
        confidence += 5
    confidence = min(confidence, 90)

    if confidence < min_confidence:
        return no_signal(f"Confidence {confidence} below minimum {min_confidence}")

    return {
        "symbol": symbol,
        "signal": direction,
        "status": "SIGNAL",
        "side": direction,
        "strategy_profile": profile_name,
        "entry": round(entry, 8),
        "tp1": round(tp1, 8),
        "tp2": round(tp2, 8),
        "tp3": round(tp3, 8),
        "sl": round(stop_loss, 8),
        "stop_loss": round(stop_loss, 8),
        "take_profit": round(tp1, 8),
        "rr": float(rr),
        "confidence": confidence,
        "confidence_score": confidence,
        "capital": round(capital, 2),
        "capital_usdt": round(capital, 2),
        "risk_percent": float(risk_percent),
        "risk_amount": round(risk_amount, 8),
        "risk_budget_usdt": round(risk_amount, 8),
        "estimated_loss": round(estimated_loss, 8),
        "estimated_risk_at_sl_usdt": round(estimated_loss, 8),
        "position_qty": round(position_qty, 8),
        "position_value": round(notional, 8),
        "notional_usdt": round(notional, 8),
        "margin_usdt": round(margin_usdt, 4),
        "stop_distance_pct": round(stop_pct * 100, 3),
        "estimated_profit_tp1_usdt": round(profit_tp1, 8),
        "estimated_profit_tp2_usdt": round(profit_tp2, 8),
        "max_leverage": float(max_leverage),
        "leverage": float(leverage_used),
        "trend": trend,
        "trend_1h": trend,
        "reason": (
            f"{trend_tf} trend + {entry_tf} EMA{entry_fast_period} pullback/"
            + ("reclaim" if direction == "LONG" else "rejection")
            + (" + volume confirmation" if volume_confirmed else "")
            + f" · {cfg['label']} profile"
        ),
        "timeframe_entry": entry_tf,
        "timeframe_trend": trend_tf,
        "indicators": indicators_out,
    }
