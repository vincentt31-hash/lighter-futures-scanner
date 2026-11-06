# CUAN SCANNER V2 — Backend Foundation

This folder contains the V2 FastAPI backend foundation.

## Market-data architecture

- Provider: Bybit Indonesia V5 public market-data API.
- New V2 market feed: USDT linear category.
- Configured candidate instruments: BTCUSDT, XAUUSDT, XAUTUSDT. The backend validates each instrument against live exchange metadata; availability is not assumed.
- REST market data and public WebSocket stream; no API key is required for these public endpoints.
- No order placement, account access, or authenticated Futures execution.

## V2 market endpoints

- `GET /health` — backend and market-data connection state.
- `GET /market/symbols` — validates configured symbols against live linear instrument metadata.
- `GET /market/overview` — latest in-memory ticker and kline snapshots.
- `GET /market/klines/{symbol}?interval=15&limit=200` — normalized historical candles.
- `WS /ws/market` — public ticker and kline events for connected clients.
- `GET /docs` — interactive API documentation.

Supported market-manager intervals: `1`, `5`, `15`, `60`, `240`, and `D`.

## Legacy scanner compatibility

The existing `/scan`, `/watchlist`, and `/prices` routes are retained for compatibility. They still use the legacy spot-market adapter and the existing 1H/15M day-trade strategy. They are **not yet migrated** to the new USDT linear market feed. The scanner remains signal-only.

The strategy module and its response shape should be preserved while the market-data adapter and signal timeframes are migrated in a separate step. The earlier 1M/5M scalping plan is not yet reflected in the current legacy `/scan` endpoint.

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

## Current scope

Phase 1 is public market-data plumbing and API integration. Signal-engine migration, risk sizing against linear contract filters, chart overlays, persistence, notifications, Android integration, and any authenticated trading features remain separate work. Do not treat a generated signal as a guaranteed trade outcome.
