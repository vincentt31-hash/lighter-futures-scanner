from __future__ import annotations

import asyncio
import logging
from collections import Counter
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .config import (
    WATCHLIST,
    DEFAULT_CAPITAL,
    DEFAULT_RISK_PERCENT,
    MAX_LEVERAGE,
    MIN_CONFIDENCE,
    AUTO_TOP_VOLUME,
    TOP_PAIR_COUNT,
    QUOTE_COIN,
)
from .bybit import tradingview_symbol
from .strategy import analyze
from .api.routes.market import router as market_router
from .api.routes.health import router as health_router
from .services.market_manager import market_manager
from .services.normalizers import normalize_rest_klines

logger = logging.getLogger(__name__)
SCAN_CONCURRENCY = 5


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop the shared Bybit public linear market-data clients."""
    try:
        await market_manager.start()
    except Exception:
        # The API can still start; market endpoints report the provider issue.
        logger.exception("Unable to start Bybit Indonesia V5 market-data manager")

    try:
        yield
    finally:
        await market_manager.stop()


app = FastAPI(
    title="CUAN SCANNER V2",
    version="2.0.0",
    description=(
        "Bybit Indonesia V5 USDT linear-perpetual signal scanner. "
        "Public market data only; no account access or order execution."
    ),
    lifespan=lifespan,
)


class ScanRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: WATCHLIST)
    auto_top_volume: bool = AUTO_TOP_VOLUME
    top_pair_count: int = Field(default=TOP_PAIR_COUNT, ge=1, le=200)
    capital_usdt: float = Field(default=DEFAULT_CAPITAL, gt=0)
    risk_percent: float = Field(default=DEFAULT_RISK_PERCENT, gt=0, le=10)
    max_leverage: float = Field(default=MAX_LEVERAGE, ge=1, le=125)
    min_confidence: int = Field(default=MIN_CONFIDENCE, ge=0, le=100)


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().replace("/", "").replace(".P", "")


def _is_active_usdt_linear_perpetual(instrument: dict) -> bool:
    return (
        instrument.get("status") == "Trading"
        and instrument.get("contractType") == "LinearPerpetual"
        and instrument.get("quoteCoin") == QUOTE_COIN
        and instrument.get("settleCoin") == QUOTE_COIN
        and bool(instrument.get("symbol"))
    )


async def get_linear_market_snapshot() -> tuple[set[str], list[dict]]:
    """Fetch the live USDT linear-perpetual universe and its public tickers."""
    await market_manager.start()
    instruments, tickers = await asyncio.gather(
        market_manager.rest.get_instruments_info(category="linear"),
        market_manager.rest.get_tickers(category="linear"),
    )
    eligible = {
        item["symbol"].upper()
        for item in instruments
        if _is_active_usdt_linear_perpetual(item)
    }
    if not eligible:
        raise RuntimeError("Bybit returned no active USDT linear perpetual instruments")
    return eligible, tickers


def _prices_from_tickers(eligible: set[str], tickers: list[dict]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for ticker in tickers:
        symbol = str(ticker.get("symbol") or "").upper()
        if symbol not in eligible:
            continue
        try:
            price = float(ticker.get("lastPrice") or 0)
        except (TypeError, ValueError):
            continue
        if price > 0:
            prices[symbol] = price
    return prices


def _select_symbols(
    request: ScanRequest,
    eligible: set[str],
    tickers: list[dict],
) -> list[str]:
    if request.auto_top_volume:
        ranked: list[tuple[str, float]] = []
        for ticker in tickers:
            symbol = str(ticker.get("symbol") or "").upper()
            if symbol not in eligible:
                continue
            try:
                turnover = float(ticker.get("turnover24h") or 0)
            except (TypeError, ValueError):
                continue
            if turnover > 0:
                ranked.append((symbol, turnover))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return [symbol for symbol, _ in ranked[:request.top_pair_count]]

    selected = (_normalize_symbol(item) for item in request.symbols)
    return list(dict.fromkeys(symbol for symbol in selected if symbol in eligible))


def _selection_name(request: ScanRequest) -> str:
    return "top_24h_usdt_turnover" if request.auto_top_volume else "manual_live_validated"


@app.get("/")
def root():
    return {
        "name": "CUAN SCANNER V2",
        "version": "2.0.0",
        "mode": "signal-only",
        "market_data_provider": "Bybit Indonesia V5",
        "market_category": "linear",
        "contract_filter": "Trading USDT LinearPerpetual",
        "market_symbols": ["BTCUSDT", "XAUUSDT", "XAUTUSDT"],
        "quote_coin": QUOTE_COIN,
        "default_watchlist": WATCHLIST,
        "strategy_profile": "day_trade",
        "timeframe_trend": "1h",
        "timeframe_entry": "15m",
        "risk_percent_default": DEFAULT_RISK_PERCENT,
        "max_leverage_default": MAX_LEVERAGE,
        "note": (
            "The scanner uses public Bybit USDT linear-perpetual market data. "
            "Signals are simulated analysis only; no orders are placed."
        ),
    }


@app.get("/watchlist")
async def watchlist():
    request = ScanRequest(auto_top_volume=AUTO_TOP_VOLUME)
    eligible, tickers = await get_linear_market_snapshot()
    symbols = _select_symbols(request, eligible, tickers)
    return {
        "symbols": symbols,
        "display_symbols": [tradingview_symbol(symbol) for symbol in symbols],
        "selection": _selection_name(request),
        "quote_coin": QUOTE_COIN,
        "market_category": "linear",
        "contract_type": "LinearPerpetual",
    }


@app.get("/prices")
async def prices():
    eligible, tickers = await get_linear_market_snapshot()
    live_prices = _prices_from_tickers(eligible, tickers)
    return {
        "quote_coin": QUOTE_COIN,
        "market_category": "linear",
        "prices": live_prices,
        "display_prices": {
            tradingview_symbol(symbol): price
            for symbol, price in live_prices.items()
        },
    }


@app.get("/scan")
async def scan_default():
    return await scan(ScanRequest())


async def scan_one(
    symbol: str,
    request: ScanRequest,
    latest_prices: dict[str, float],
    semaphore: asyncio.Semaphore,
) -> dict:
    try:
        async with semaphore:
            h1_rows, m15_rows = await asyncio.gather(
                market_manager.rest.get_klines(
                    symbol, "60", 250, category="linear"
                ),
                market_manager.rest.get_klines(
                    symbol, "15", 250, category="linear"
                ),
            )

        # REST klines are normalized into oldest-to-newest order. The strategy
        # excludes the newest (possibly still-forming) candle by default.
        h1 = [
            candle.model_dump(mode="python")
            for candle in normalize_rest_klines(h1_rows, symbol, "60")
        ]
        m15 = [
            candle.model_dump(mode="python")
            for candle in normalize_rest_klines(m15_rows, symbol, "15")
        ]

        result = analyze(
            symbol,
            h1,
            m15,
            capital=request.capital_usdt,
            risk_percent=request.risk_percent,
            max_leverage=request.max_leverage,
            min_confidence=request.min_confidence,
        )

        if symbol in latest_prices:
            result["last_price"] = latest_prices[symbol]
        result["display_symbol"] = tradingview_symbol(symbol)
        result["market_category"] = "linear"
        return result

    except Exception as exc:
        logger.exception("Linear futures scan failed for %s", symbol)
        return {
            "symbol": symbol,
            "display_symbol": tradingview_symbol(symbol),
            "status": "ERROR",
            "reason": str(exc),
            "last_price": latest_prices.get(symbol),
            "market_category": "linear",
        }


@app.post("/scan")
async def scan(request: ScanRequest):
    try:
        eligible, tickers = await get_linear_market_snapshot()
        symbols = _select_symbols(request, eligible, tickers)
        live_prices = _prices_from_tickers(eligible, tickers)
    except Exception as exc:
        logger.exception("Unable to load Bybit linear futures market data")
        return {
            "count": 0,
            "signal_count": 0,
            "selection": _selection_name(request),
            "quote_coin": QUOTE_COIN,
            "market_category": "linear",
            "error": str(exc),
            "results": [],
        }

    semaphore = asyncio.Semaphore(SCAN_CONCURRENCY)
    results = await asyncio.gather(
        *(
            scan_one(symbol, request, live_prices, semaphore)
            for symbol in symbols
        )
    )

    reason_summary = Counter(
        result.get("signal")
        if result.get("signal") in ("LONG", "SHORT")
        else (
            result.get("reason")
            or result.get("status")
            or "unknown"
        )
        for result in results
    )

    return {
        "count": len(results),
        "signal_count": sum(
            1
            for result in results
            if result.get("signal") in ("LONG", "SHORT")
        ),
        "reason_summary": dict(reason_summary.most_common()),
        "selection": _selection_name(request),
        "quote_coin": QUOTE_COIN,
        "market_category": "linear",
        "contract_type": "LinearPerpetual",
        "symbols": symbols,
        "display_symbols": [tradingview_symbol(symbol) for symbol in symbols],
        "prices": {
            symbol: live_prices[symbol]
            for symbol in symbols
            if symbol in live_prices
        },
        "results": results,
        "strategy_profile": "day_trade",
    }


# Register V2 public market-data and health routes.
app.include_router(health_router)
app.include_router(market_router)
