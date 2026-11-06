"""Named strategy profiles for CUAN Scanner V2.

Intervals are Bybit V5 interval strings. All profile stop limits are fractions
of entry price, not guarantees of realized loss or liquidation distance.
"""

STRATEGY_PROFILES = {
    "scalping": {
        "label": "Scalping",
        "trend_interval": "5",
        "entry_interval": "1",
        "trend_timeframe": "5m",
        "entry_timeframe": "1m",
        "trend_fast_ema": 20,
        "trend_slow_ema": 50,
        "entry_fast_ema": 9,
        "entry_slow_ema": 21,
        "rsi_long": (48, 70),
        "rsi_short": (30, 52),
        "rsi_bonus_long": (53, 66),
        "rsi_bonus_short": (34, 47),
        "min_stop_pct": 0.002,
        "max_stop_pct": 0.012,
        "atr_floor_mult": 1.2,
        "atr_cap_mult": 3.0,
        "swing_lookback": 12,
        "swing_atr_buffer": 0.35,
        "pullback_lookback": 4,
        "max_entry_range_atr": 2.5,
        "min_trend_candles": 55,
        "min_entry_candles": 40,
        "description": "5m trend filter with 1m pullback/reclaim entry",
    },
    "day_trade": {
        "label": "Day Trade",
        "trend_interval": "60",
        "entry_interval": "15",
        "trend_timeframe": "1h",
        "entry_timeframe": "15m",
        "trend_fast_ema": 20,
        "trend_slow_ema": 50,
        "entry_fast_ema": 9,
        "entry_slow_ema": 21,
        "rsi_long": (45, 70),
        "rsi_short": (30, 55),
        "rsi_bonus_long": (52, 65),
        "rsi_bonus_short": (35, 48),
        "min_stop_pct": 0.02,
        "max_stop_pct": 0.08,
        "atr_floor_mult": 2.0,
        "atr_cap_mult": 4.0,
        "swing_lookback": 12,
        "swing_atr_buffer": 0.5,
        "pullback_lookback": 4,
        "max_entry_range_atr": 2.5,
        "min_trend_candles": 55,
        "min_entry_candles": 40,
        "description": "1h trend filter with 15m pullback/reclaim entry",
    },
    "swing": {
        "label": "Swing",
        "trend_interval": "240",
        "entry_interval": "60",
        "trend_timeframe": "4h",
        "entry_timeframe": "1h",
        "trend_fast_ema": 20,
        "trend_slow_ema": 50,
        "entry_fast_ema": 9,
        "entry_slow_ema": 21,
        "rsi_long": (45, 68),
        "rsi_short": (32, 55),
        "rsi_bonus_long": (50, 64),
        "rsi_bonus_short": (36, 49),
        "min_stop_pct": 0.01,
        "max_stop_pct": 0.12,
        "atr_floor_mult": 1.5,
        "atr_cap_mult": 4.0,
        "swing_lookback": 8,
        "swing_atr_buffer": 0.5,
        "pullback_lookback": 5,
        "max_entry_range_atr": 3.0,
        "min_trend_candles": 55,
        "min_entry_candles": 40,
        "description": "4h trend filter with 1h pullback/reclaim entry",
    },
}


def get_strategy_profile(name: str) -> dict:
    """Return a copy of a supported profile or raise ValueError."""
    key = str(name or "day_trade").strip().lower()
    if key not in STRATEGY_PROFILES:
        supported = ", ".join(STRATEGY_PROFILES)
        raise ValueError(f"Unknown strategy profile '{key}'. Choose: {supported}")
    return dict(STRATEGY_PROFILES[key])


def list_strategy_profiles() -> list[dict]:
    """Return API-safe profile descriptions without mutable nested settings."""
    return [
        {
            "id": key,
            "label": value["label"],
            "timeframe_trend": value["trend_timeframe"],
            "timeframe_entry": value["entry_timeframe"],
            "description": value["description"],
        }
        for key, value in STRATEGY_PROFILES.items()
    ]
