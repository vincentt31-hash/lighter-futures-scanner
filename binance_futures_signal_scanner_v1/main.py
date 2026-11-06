from __future__ import annotations

import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from .bybit import (
    get_klines,
    get_active_usdc_perpetual_symbols,
    get_usdc_perpetual_prices,
    tradingview_symbol,
)
from .strategy import analyze

# New CUAN SCANNER V2 public linear market-data modules.
from .api.routes.market import router as market_router
from .api.routes.health import router as health_router
from .services.market_manager import market_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop the V2 market-data manager with the FastAPI application."""
    try:
        await market_manager.start()
    except Exception:
        # Keep the existing scanner API available if the new market-data
        # provider is temporarily unreachable. /health reports its state.
        logger.exception("Unable to start V2 Bybit market-data manager")

    try:
        yield
    finally:
        await market_manager.stop()


app = FastAPI(
    title="CUAN SCANNER V2",
    version="2.0.0",
    description=(
        "Bybit Indonesia market-data foundation and legacy signal scanner. "
        "Signal-only; no order execution."
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


def get_active_symbols(request: ScanRequest):
    # NOTE: This is the EXISTING/LEGACY scanner selection and still follows
    # the quote-coin configuration in config.py. It is not yet migrated to
    # the new BTCUSDT/XAUUSDT/XAUTUSDT linear market-data registry.
    if request.auto_top_volume:
        return get_active_usdc_perpetual_symbols(request.top_pair_count)

    live = set(get_active_usdc_perpetual_symbols(10000))
    return [
        symbol
        for symbol in (_normalize_symbol(item) for item in request.symbols)
        if symbol in live
    ]


@app.get("/")
def root():
    return {
        "name": "CUAN SCANNER V2",
        "version": "2.0.0",
        "mode": "signal-only",
        "market_data_provider": "Bybit Indonesia V5",
        "new_market_category": "linear",
        "new_market_symbols": ["BTCUSDT", "XAUUSDT", "XAUTUSDT"],
        "legacy_scanner_quote_coin": QUOTE_COIN,
        "legacy_watchlist": WATCHLIST,
        "note": (
            "The /market endpoints use the new linear market-data manager. "
            "The existing /scan, /watchlist and /prices endpoints retain "
            "their previous implementation until separately migrated."
        ),
    }


@app.get("/watchlist")
def watchlist():
    symbols = (
        get_active_usdc_perpetual_symbols(TOP_PAIR_COUNT)
        if AUTO_TOP_VOLUME
        else get_active_symbols(ScanRequest(auto_top_volume=False))
    )
    return {
        "symbols": symbols,
        "display_symbols": [tradingview_symbol(symbol) for symbol in symbols],
        "selection": (
            "top_24h_turnover"
            if AUTO_TOP_VOLUME
            else "manual_live_validated"
        ),
        "quote_coin": QUOTE_COIN,
        "legacy_endpoint": True,
    }


@app.get("/prices")
def prices():
    live_prices = get_usdc_perpetual_prices()
    return {
        "quote_coin": QUOTE_COIN,
        "prices": live_prices,
        "display_prices": {
            tradingview_symbol(symbol): price
            for symbol, price in live_prices.items()
        },
        "legacy_endpoint": True,
    }


@app.get("/scan")
def scan_default():
    return scan(ScanRequest())


def scan_one(symbol, request, latest_prices):
    try:
        h1 = get_klines(symbol, "1h", 250)
        m15 = get_klines(symbol, "15m", 250)
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
        return result

    except Exception as exc:
        logger.exception("Legacy scan failed for %s", symbol)
        return {
            "symbol": symbol,
            "display_symbol": tradingview_symbol(symbol),
            "status": "ERROR",
            "reason": str(exc),
            "last_price": latest_prices.get(symbol),
        }


@app.post("/scan")
def scan(request: ScanRequest):
    try:
        symbols = get_active_symbols(request)
        live_prices = get_usdc_perpetual_prices()
    except Exception as exc:
        logger.exception("Unable to load legacy scanner market data")
        return {
            "count": 0,
            "selection": (
                "top_24h_turnover"
                if request.auto_top_volume
                else "manual_live_validated"
            ),
            "quote_coin": QUOTE_COIN,
            "error": str(exc),
            "results": [],
        }

    results_by_symbol = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(scan_one, symbol, request, live_prices): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            results_by_symbol[symbol] = future.result()

    results = [results_by_symbol[symbol] for symbol in symbols]

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
        "selection": (
            "top_24h_turnover"
            if request.auto_top_volume
            else "manual_live_validated"
        ),
        "quote_coin": QUOTE_COIN,
        "symbols": symbols,
        "display_symbols": [tradingview_symbol(symbol) for symbol in symbols],
        "prices": {
            symbol: live_prices[symbol]
            for symbol in symbols
            if symbol in live_prices
        },
        "results": results,
        "legacy_endpoint": True,
    }


# Register the new V2 routes. The new health router owns GET /health.
app.include_router(health_router)
app.include_router(market_router)
