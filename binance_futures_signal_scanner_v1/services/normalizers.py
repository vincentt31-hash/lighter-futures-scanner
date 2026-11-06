from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.market import Candle, MarketEvent, Ticker


def to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def utc_from_ms(value: Any) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


def normalize_rest_klines(
    rows: list[list[Any]],
    symbol: str,
    interval: str,
) -> list[Candle]:
    """Bybit REST kline rows are newest-first and have no confirm flag."""
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    interval_ms = interval_to_milliseconds(interval)
    candles: list[Candle] = []

    for row in rows:
        if len(row) < 7:
            continue
        start_ms = int(row[0])
        candles.append(Candle(
            symbol=symbol.upper(),
            interval=interval,
            start_time=utc_from_ms(start_ms),
            open=Decimal(str(row[1])),
            high=Decimal(str(row[2])),
            low=Decimal(str(row[3])),
            close=Decimal(str(row[4])),
            volume=Decimal(str(row[5])),
            turnover=Decimal(str(row[6])),
            is_closed=(start_ms + interval_ms <= now_ms),
            source="bybit",
        ))

    return sorted(candles, key=lambda candle: candle.start_time)


def normalize_ws_kline(message: dict[str, Any]) -> list[Candle]:
    topic = message.get("topic", "")
    parts = topic.split(".")
    if len(parts) != 3 or parts[0] != "kline":
        return []

    interval, symbol = parts[1], parts[2]
    result: list[Candle] = []

    for item in message.get("data", []):
        result.append(Candle(
            symbol=symbol,
            interval=interval,
            start_time=utc_from_ms(item["start"]),
            open=Decimal(str(item["open"])),
            high=Decimal(str(item["high"])),
            low=Decimal(str(item["low"])),
            close=Decimal(str(item["close"])),
            volume=Decimal(str(item["volume"])),
            turnover=to_decimal(item.get("turnover")),
            is_closed=bool(item.get("confirm", False)),
            source="bybit",
        ))
    return result


def normalize_ws_ticker(message: dict[str, Any]) -> Ticker | None:
    topic = message.get("topic", "")
    if not topic.startswith("tickers."):
        return None

    symbol = topic.split(".", 1)[1]
    data = message.get("data", {})
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        return None

    return Ticker(
        symbol=symbol,
        last_price=to_decimal(data.get("lastPrice")),
        mark_price=to_decimal(data.get("markPrice")),
        index_price=to_decimal(data.get("indexPrice")),
        price_24h_pct=to_decimal(data.get("price24hPcnt")),
        turnover_24h=to_decimal(data.get("turnover24h")),
        volume_24h=to_decimal(data.get("volume24h")),
        timestamp_ms=int(message.get("ts") or data.get("ts") or 0),
        source="bybit",
    )


def interval_to_milliseconds(interval: str) -> int:
    if interval in {"D", "W", "M"}:
        return {"D": 86_400_000, "W": 604_800_000, "M": 2_592_000_000}[interval]
    try:
        return int(interval) * 60_000
    except ValueError as exc:
        raise ValueError(f"Unsupported Bybit interval: {interval}") from exc


def make_market_event(payload: Candle | Ticker) -> MarketEvent:
    return MarketEvent(
        event_type="kline" if isinstance(payload, Candle) else "ticker",
        symbol=payload.symbol,
        timestamp=datetime.now(timezone.utc),
        candle=payload if isinstance(payload, Candle) else None,
        ticker=payload if isinstance(payload, Ticker) else None,
    )
