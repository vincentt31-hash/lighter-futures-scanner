from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)
MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


class BybitWebSocket:
    """Reconnectable public linear WebSocket client for Bybit Indonesia."""

    def __init__(
        self,
        base_url: str = "wss://stream.bybit.id/v5/public/linear",
        on_message: MessageHandler | None = None,
    ) -> None:
        self.base_url = base_url
        self.on_message = on_message
        self._running = False
        self._ws = None
        self._topics: list[str] = []

    @staticmethod
    def build_topics(
        symbols: Sequence[str],
        intervals: Sequence[str],
        include_tickers: bool = True,
    ) -> list[str]:
        topics: list[str] = []
        for symbol in symbols:
            symbol = symbol.upper()
            if include_tickers:
                topics.append(f"tickers.{symbol}")
            topics.extend(f"kline.{interval}.{symbol}" for interval in intervals)
        return topics

    async def _heartbeat(self) -> None:
        while self._running and self._ws is not None:
            try:
                await self._ws.send(json.dumps({"op": "ping"}))
            except Exception:
                logger.exception("Bybit WebSocket heartbeat failed")
                return
            await asyncio.sleep(20)

    async def run(
        self,
        topics: Sequence[str],
        on_message: MessageHandler | None = None,
    ) -> None:
        self._topics = list(dict.fromkeys(topics))
        handler = on_message or self.on_message
        if handler is None:
            raise ValueError("A WebSocket message handler is required")

        self._running = True
        retry_delay = 1.0

        while self._running:
            heartbeat_task = None
            try:
                async with websockets.connect(
                    self.base_url,
                    ping_interval=None,  # Use Bybit JSON heartbeat.
                    close_timeout=5,
                    max_size=2**20,
                ) as ws:
                    self._ws = ws
                    await ws.send(json.dumps({
                        "op": "subscribe",
                        "args": self._topics,
                    }))
                    logger.info("Subscribed to %d Bybit topics", len(self._topics))
                    retry_delay = 1.0
                    heartbeat_task = asyncio.create_task(self._heartbeat())

                    async for raw_message in ws:
                        message = json.loads(raw_message)
                        if message.get("op") in {"ping", "subscribe"}:
                            continue
                        await handler(message)

            except asyncio.CancelledError:
                raise
            except (ConnectionClosed, OSError, asyncio.TimeoutError):
                logger.warning("Bybit WebSocket disconnected; reconnecting")
            except Exception:
                logger.exception("Bybit WebSocket error; reconnecting")
            finally:
                self._ws = None
                if heartbeat_task:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass

            if self._running:
                await asyncio.sleep(retry_delay + random.uniform(0, 0.4))
                retry_delay = min(retry_delay * 2, 30.0)

    async def stop(self) -> None:
        self._running = False
        if self._ws is not None:
            await self._ws.close()
