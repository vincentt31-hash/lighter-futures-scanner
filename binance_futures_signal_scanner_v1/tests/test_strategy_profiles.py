import unittest

from binance_futures_signal_scanner_v1.strategy import analyze
from binance_futures_signal_scanner_v1.market_structure import detect_fvg, find_swings
from binance_futures_signal_scanner_v1.risk_engine import size_linear_position
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

    def _instrument(self, min_notional="5"):
        return {
            "lotSizeFilter": {
                "qtyStep": "0.001",
                "minOrderQty": "0.001",
                "minNotionalValue": min_notional,
            },
            "priceFilter": {"tickSize": "0.5"},
        }

    def test_long_risk_size_respects_steps_and_risk_budget(self):
        result = size_linear_position(
            side="LONG", entry="100", stop_loss="95.12",
            capital_usdt="1000", risk_percent="1", max_leverage="20",
            instrument=self._instrument(), take_profits=["110.1"],
        )
        self.assertTrue(result["tradeable_size"])
        self.assertEqual(result["entry_rounded"], "100")
        self.assertEqual(result["stop_loss_rounded"], "95.5")
        self.assertEqual(result["take_profits_rounded"], ["110.5"])
        self.assertEqual(result["quantity"], "2.222")
        self.assertLessEqual(float(result["estimated_loss_at_stop_usdt"]), 10.0)

    def test_short_risk_size_rounds_stop_toward_entry(self):
        result = size_linear_position(
            side="SHORT", entry="100", stop_loss="105.12",
            capital_usdt="1000", risk_percent="1", max_leverage="20",
            instrument=self._instrument(), take_profits=["90.1"],
        )
        self.assertTrue(result["tradeable_size"])
        self.assertEqual(result["stop_loss_rounded"], "105")
        self.assertEqual(result["take_profits_rounded"], ["90"])

    def test_rejects_below_minimum_notional(self):
        result = size_linear_position(
            side="LONG", entry="100", stop_loss="99",
            capital_usdt="1", risk_percent="1", max_leverage="2",
            instrument=self._instrument(min_notional="5"),
        )
        self.assertFalse(result["tradeable_size"])
        self.assertTrue(any("minNotionalValue" in item for item in result["validation_errors"]))

    def test_rejects_wrong_side_stop(self):
        with self.assertRaises(ValueError):
            size_linear_position(
                side="LONG", entry="100", stop_loss="101",
                capital_usdt="100", risk_percent="1", max_leverage="5",
                instrument=self._instrument(),
            )


if __name__ == "__main__":
    unittest.main()
