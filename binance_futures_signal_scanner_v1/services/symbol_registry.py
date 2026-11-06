from __future__ import annotations

from app.models.market import InstrumentStatus


class SymbolRegistry:
    """Validates configured symbols against Bybit's live linear instruments."""

    DEFAULT_SYMBOLS = ("BTCUSDT", "XAUUSDT", "XAUTUSDT")

    def __init__(self, required_symbols: tuple[str, ...] | None = None) -> None:
        self.required_symbols = tuple(
            symbol.upper() for symbol in (required_symbols or self.DEFAULT_SYMBOLS)
        )
        self._instruments: dict[str, dict] = {}

    def refresh(self, instruments: list[dict]) -> dict[str, InstrumentStatus]:
        self._instruments = {
            item.get("symbol", "").upper(): item
            for item in instruments
            if item.get("symbol")
        }

        result: dict[str, InstrumentStatus] = {}
        for symbol in self.required_symbols:
            item = self._instruments.get(symbol)

            if item is None:
                result[symbol] = InstrumentStatus(
                    symbol=symbol,
                    available=False,
                    reason="Contract not listed in Bybit linear instruments",
                )
                continue

            status = item.get("status")
            contract_type = item.get("contractType")
            quote_coin = item.get("quoteCoin")
            settle_coin = item.get("settleCoin")
            is_valid = (
                status == "Trading"
                and contract_type == "LinearPerpetual"
                and quote_coin == "USDT"
                and settle_coin == "USDT"
            )

            lot_filter = item.get("lotSizeFilter") or {}
            price_filter = item.get("priceFilter") or {}

            result[symbol] = InstrumentStatus(
                symbol=symbol,
                available=is_valid,
                status=status,
                contract_type=contract_type,
                quote_coin=quote_coin,
                settle_coin=settle_coin,
                tick_size=price_filter.get("tickSize"),
                qty_step=lot_filter.get("qtyStep"),
                min_order_qty=lot_filter.get("minOrderQty"),
                reason=None if is_valid else "Not an active USDT linear perpetual contract",
            )

        return result

    def is_available(self, symbol: str) -> bool:
        item = self._instruments.get(symbol.upper())
        return bool(
            item
            and item.get("status") == "Trading"
            and item.get("contractType") == "LinearPerpetual"
            and item.get("quoteCoin") == "USDT"
            and item.get("settleCoin") == "USDT"
        )

    def get_instrument(self, symbol: str) -> dict | None:
        return self._instruments.get(symbol.upper())

    def available_symbols(self) -> list[str]:
        return [symbol for symbol in self.required_symbols if self.is_available(symbol)]
