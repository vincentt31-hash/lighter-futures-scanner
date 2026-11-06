# CUAN SCANNER V2 — Backend Foundation

This folder contains the V2 FastAPI backend.

## Market-data architecture

- Provider: Bybit Indonesia V5 public market-data API.
- Scanner market category: USDT linear perpetual contracts.
- V2 market-data focus symbols: BTCUSDT, XAUUSDT, and XAUTUSDT. The market endpoint validates each against live instrument metadata; availability is not assumed.
- The scanner can also select the highest 24-hour USDT turnover linear perpetual pairs, or use the manual watchlist.
- REST and public WebSocket market data only. No API key, account access, or order execution is used.
- Regional endpoints default to `https://api.bybit.id` and `wss://stream.bybit.id/v5/public/linear`; override them with `BYBIT_BASE_URL` and `BYBIT_WS_URL` when needed.

## Scanner endpoints

- `GET /health` — backend and market-data connection state.
- `GET /watchlist` — current eligible linear perpetual symbols, ranked by 24-hour turnover or filtered from the manual watchlist.
- `GET /prices` — current public ticker prices for eligible USDT linear perpetuals.
- `GET /scan` — run the default signal scan.
- `POST /scan` — run a scan with custom symbols, capital, risk, leverage cap, and confidence threshold.
- `GET /docs` — interactive API documentation.

## V2 live market endpoints

- `GET /market/symbols` — validates the configured focus symbols against live linear instrument metadata.
- `GET /market/overview` — latest in-memory ticker and kline snapshots.
- `GET /market/klines/{symbol}?interval=15&limit=200` — normalized historical candles.
- `WS /ws/market` — public ticker and kline events for connected clients.

Supported market-manager intervals: `1`, `5`, `15`, `60`, `240`, and `D`.

## Strategy profiles

Use `POST /scan` with a `profile` field, or inspect `GET /strategy/profiles`.

| Profile | Trend timeframe | Entry timeframe |
|---|---:|---:|
| `scalping` | 5M | 1M |
| `day_trade` (default) | 1H | 15M |
| `swing` | 4H | 1H |

Each profile has independent RSI bands, pullback lookback, ATR stop multipliers, stop-distance bounds, and swing lookback. All profiles use closed candles, EMA/RSI/ATR, pullback/reclaim or rejection, and a soft volume confirmation factor. Legacy indicator field names are retained as aliases for existing Android clients; the new generic indicator fields identify the active profile's actual timeframes.

Every result now also includes `market_structure.trend_timeframe` and `market_structure.entry_timeframe` annotations: confirmed fractal swing highs/lows, structural bias, BOS/CHoCH event, buy-side/sell-side liquidity sweep, recent FVG zones, and recent support/resistance pivot levels. These are deterministic OHLCV heuristics, not exchange-provided order-flow data.

Example request:

```json
{
  "symbols": ["BTCUSDT", "XAUUSDT", "XAUTUSDT"],
  "auto_top_volume": false,
  "profile": "scalping",
  "capital_usdt": 100,
  "risk_percent": 1,
  "max_leverage": 20,
  "min_confidence": 60
}
```

Default risk budget: 1% of capital. Leverage is derived from stop distance and capped by the configured maximum plus a conservative heuristic; this is not an exchange liquidation calculation. TP targets are at least 2R (TP1), followed by 3R and 4R extensions. Position size may be capped by the leverage limit, so estimated loss can be lower than the requested risk budget.

These profiles are initial rule-based configurations, not backtested or optimized performance claims. Scalping can be especially sensitive to fees, spread, slippage, and latency; paper-test each profile before relying on it.

## Run on Windows

From the repository root, run `binance_futures_signal_scanner_v1/run_windows.bat`.

Or run manually from the repository root:

```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r binance_futures_signal_scanner_v1\requirements.txt
uvicorn binance_futures_signal_scanner_v1.main:app --host 127.0.0.1 --port 8000 --reload
```

Then open `http://127.0.0.1:8000/docs`.

## Important scope

This is a signal-only scanner. It does not authenticate to a trading account, place or manage orders, or guarantee execution or outcomes. The new linear feed and scanner data adapter are integrated, but live runtime validation against the exchange and Android-client integration still need to be tested.
