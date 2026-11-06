import os

# Bybit Indonesia V5 API base URL; override with BYBIT_BASE_URL if needed.
BASE_URL = os.getenv("BYBIT_BASE_URL", "https://api.bybit.id").rstrip("/")
WS_BASE_URL = os.getenv(
    "BYBIT_WS_URL", "wss://stream.bybit.id/v5/public/linear"
).rstrip("/")

DEFAULT_CAPITAL = float(os.getenv("CAPITAL_USDT", "100"))
DEFAULT_RISK_PERCENT = float(os.getenv("RISK_PERCENT", "1"))
MAX_LEVERAGE = float(os.getenv("MAX_LEVERAGE", "20"))
# New scoring: base 60, max 90. 75 filters out many valid setups.
MIN_CONFIDENCE = int(os.getenv("MIN_CONFIDENCE", "60"))

# Manual watchlist for active Bybit Indonesia USDT linear perpetual pairs.
WATCHLIST = [
    s.strip().upper().replace("/", "").replace(".P", "")
    for s in os.getenv("WATCHLIST", "BTCUSDT,XAUUSDT,XAUTUSDT").split(",")
    if s.strip()
]
AUTO_TOP_VOLUME = os.getenv("AUTO_TOP_VOLUME", "true").lower() in ("1", "true", "yes")
TOP_PAIR_COUNT = int(os.getenv("TOP_PAIR_COUNT", "50"))
QUOTE_COIN = "USDT"
