from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from app.models.market import Candle, MarketEvent, Ticker
from app.services.bybit_rest import BybitREST
from app.services.bybit_websocket import BybitWebSocket
from app.services.normalizers import (
    make_market_event,
    normalize_rest_klines,
    normalize_ws_kline,
    normalize_ws_ticker,
)
from app.services.symbol_registry import SymbolRegistry

logger = logging.getLogger(__name__)


class MarketManager:
    def __init__(
        self,
        rest_base_url: str = "https://api.bybit.id",
        ws_base_url: str = "wss://stream.bybit.id/v5/public/linear",
        symbols: tuple[str, ...] = ("BTCUSDT", "XAUUSDT", "XAUTUSDT"),
        intervals: tuple[str, ...] = ("1", "5", "15", "60", "240", "D"),
    ) -> None:
        self.symbols = tuple(symbol.upper() for symbol in symbols)
        self.intervals = intervals
        self.rest = BybitREST(rest_base_url)
        self.registry = SymbolRegistry(self.symbols)
        self.websocket = BybitWebSocket(ws_base_url, self._handle_ws_message)
        self._ws_task: asyncio.Task | None = None
        self._started = False
        self._last_events: dict[str, dict[str, Any]] = defaultdict(dict)
        self._subscribers: set[asyncio.Queue[MarketEvent]] = set()
        self._status: dict[str, Any] = {
            "rest": "disconnected",
            "websocket": "disconnected",
            "symbols_validated": False,
        }

    async def start(self) -> None:
        if self._started:
            return
        await self.rest.start()
        self._status["rest"] = "connected"

        instruments = await self.rest.get_instruments_info(category="linear")
        self.registry.refresh(instruments)
        self._status["symbols_validated"] = True
        self._status["available_symbols"] = self.registry.available_symbols()

        available = self.registry.available_symbols()
        if available:
            topics = self.websocket.build_topics(
                available, self.intervals, include_tickers=True
            )
            self._ws_task = asyncio.create_task(
                self.websocket.run(topics),
                name="bybit-public-market-websocket",
            )
            self._status["websocket"] = "connecting"
        else:
            logger.warning("None of the configured symbols is available on Bybit linear.")

        self._started = True

    async def stop(self) -> None:
        if self._ws_task:
            await self.websocket.stop()
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
        await self.rest.close()
        self._started = False
        self._status["rest"] = "disconnected"
        self._status["websocket"] = "disconnected"

    async def _handle_ws_message(self, message: dict[str, Any]) -> None:
        topic = message.get("topic", "")
        if topic.startswith("kline."):
            for candle in normalize_ws_kline(message):
                self._last_events[candle.symbol][f"kline_{candle.interval}"] = candle
                await self._publish(make_market_event(candle))
        elif topic.startswith("tickers."):
            ticker = normalize_ws_ticker(message)
            if ticker:
                self._last_events[ticker.symbol]["ticker"] = ticker
                self._status["websocket"] = "connected"
                await self._publish(make_market_event(ticker))

    async def _publish(self, event: MarketEvent) -> None:
        stale: list[asyncio.Queue[MarketEvent]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            # Drop the oldest event so a slow UI receives the latest market state.
            try:
                queue.get_nowait()
                queue.put_nowait(event)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                pass

    def subscribe(self, maxsize: int = 200) -> asyncio.Queue[MarketEvent]:
        queue: asyncio.Queue[MarketEvent] = asyncio.Queue(maxsize=maxsize)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[MarketEvent]) -> None:
        self._subscribers.discard(queue)

    async def get_symbol_status(self) -> dict[str, Any]:
        if not self._started:
            await self.start()
        statuses = self.registry.refresh(
            await self.rest.get_instruments_info(category="linear")
        )
        return {
            symbol: status.model_dump(mode="json")
            for symbol, status in statuses.items()
        }

    async def get_klines(self, symbol: str, interval: str, limit: int = 200) -> list[dict]:
        if not self._started:
            await self.start()
        if symbol not in self.symbols:
            raise ValueError(f"Unsupported configured symbol: {symbol}")
        if interval not in self.intervals:
            raise ValueError(f"Unsupported interval: {interval}")
        if not self.registry.is_available(symbol):
            raise LookupError(f"{symbol} is not available as a Bybit USDT perpetual.")

        rows = await self.rest.get_klines(symbol, interval, limit, category="linear")
        candles = normalize_rest_klines(rows, symbol, interval)
        return [candle.model_dump(mode="json") for candle in candles]

    async def get_overview(self) -> dict[str, Any]:
        if not self._started:
            await self.start()
        return {
            "provider": "bybit-indonesia",
            "category": "linear",
            "symbols": {
                symbol: {
                    key: value.model_dump(mode="json")
                    for key, value in self._last_events.get(symbol, {}).items()
                }
                for symbol in self.symbols
            },
            "connection": self.health(),
        }

    def health(self) -> dict[str, Any]:
        return {
            **self._status,
            "subscribers": len(self._subscribers),
        }


market_manager = MarketManager()
