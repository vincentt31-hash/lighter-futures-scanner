from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Candle(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: str})

    symbol: str
    interval: str
    start_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    turnover: Decimal | None = None
    is_closed: bool
    source: str = "bybit"


class Ticker(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: str})

    symbol: str
    last_price: Decimal | None = None
    mark_price: Decimal | None = None
    index_price: Decimal | None = None
    price_24h_pct: Decimal | None = None
    turnover_24h: Decimal | None = None
    volume_24h: Decimal | None = None
    timestamp_ms: int = 0
    source: str = "bybit"


class MarketEvent(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: str})

    event_type: Literal["kline", "ticker"]
    symbol: str
    timestamp: datetime
    candle: Candle | None = None
    ticker: Ticker | None = None


class InstrumentStatus(BaseModel):
    symbol: str
    available: bool
    status: str | None = None
    contract_type: str | None = None
    quote_coin: str | None = None
    settle_coin: str | None = None
    tick_size: str | None = None
    qty_step: str | None = None
    min_order_qty: str | None = None
    reason: str | None = None
