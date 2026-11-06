# CUAN SCANNER V2 — Backend Foundation

This folder contains the V2 FastAPI backend.

## Market-data architecture

- Provider: Bybit Indonesia V5 public market-data API.
- Scanner market category: USDT linear perpetual contracts.
- V2 market-data focus symbols: BTCUSDT, XAUUSDT, and XAUTUSDT. The market endpoint validates each against live instrument metadata; availability is not assumed.
- The scanner can also select the highest 24-hour USDT turnover linear perpetual pairs, or use the manual watchlist.
- REST and public WebSocket market data only. No API key, account access, or order execution is used.

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

## Current signal strategy

The current scanner strategy is the preserved **day-trade** profile:

- Trend filter: 1H.
- Entry trigger: 15M.
- Uses closed candles, EMA/RSI/ATR, pullback and volume confirmation.
- Default risk budget: 1% of capital.
- Leverage is derived from stop distance and capped by the configured maximum and the strategy's liquidation-safety heuristic.
- TP targets are at least 2R (TP1), followed by 3R and 4R extensions.

Scalping (1M/5M) and swing-trade profiles are not implemented yet. The strategy's current stop-distance, confidence, and risk-sizing rules remain unchanged by the market-data migration.

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
