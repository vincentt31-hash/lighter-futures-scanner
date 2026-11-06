import unittest

from binance_futures_signal_scanner_v1.strategy import analyze
from binance_futures_signal_scanner_v1.market_structure import detect_fvg, find_swings
from binance_futures_signal_scanner_v1.strategy_profiles import (
    get_strategy_profile,
    list_strategy_profiles,
)


class StrategyProfileTests(unittest.TestCase):
    def test_profile_timeframe_mapping(self):
        expected = {
            "scalping": ("5m", "1m", "5", "1"),
            "day_trade": ("1h", "15m", "60", "15"),
            "swing": ("4h", "1h", "240", "60"),
        }
        for name, values in expected.items():
            with self.subTest(profile=name):
                cfg = get_strategy_profile(name)
                self.assertEqual(
                    (
                        cfg["trend_timeframe"],
                        cfg["entry_timeframe"],
                        cfg["trend_interval"],
                        cfg["entry_interval"],
                    ),
                    values,
                )

    def test_default_profile_is_day_trade(self):
        self.assertEqual(get_strategy_profile("day_trade")["entry_interval"], "15")

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(ValueError):
            get_strategy_profile("position-trading")

    def test_empty_market_data_returns_profile_specific_no_signal(self):
        result = analyze("BTCUSDT", [], [], profile="scalping")
        self.assertEqual(result["signal"], "NO_SIGNAL")
        self.assertEqual(result["strategy_profile"], "scalping")
        self.assertEqual(result["timeframe_trend"], "5m")
        self.assertEqual(result["timeframe_entry"], "1m")

    def test_profile_list_contains_three_modes(self):
        self.assertEqual(
            [item["id"] for item in list_strategy_profiles()],
            ["scalping", "day_trade", "swing"],
        )

    def test_bullish_fvg_is_detected(self):
        candles = [
            {"high": 10, "low": 8},
            {"high": 11, "low": 9},
            {"high": 13, "low": 12},
        ]
        gaps = detect_fvg(candles)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["type"], "BULLISH_FVG")
        self.assertEqual((gaps[0]["lower"], gaps[0]["upper"]), (10.0, 12.0))

    def test_fractal_swing_high_is_confirmed(self):
        values = [5, 6, 8, 7, 6, 5, 6]
        candles = [{"high": v, "low": v - 2} for v in values]
        swings = find_swings(candles, left=2, right=2)
        self.assertEqual(swings["highs"][0]["index"], 2)
        self.assertEqual(swings["highs"][0]["price"], 8.0)


if __name__ == "__main__":
    unittest.main()
