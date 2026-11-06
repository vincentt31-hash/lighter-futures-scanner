from __future__ import annotations

from typing import Any

import httpx


class BybitAPIError(RuntimeError):
    """Raised when Bybit returns an API error or an invalid response."""


class BybitREST:
    """Async client for Bybit V5 public market-data endpoints.

    Public market endpoints do not require API keys.
    """

    def __init__(
        self,
        base_url: str = "https://api.bybit.id",
        timeout: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"User-Agent": "CuanScannerV2/2.0"},
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            await self.start()
        assert self._client is not None

        response = await self._client.get(path, params=params)
        response.raise_for_status()
        payload = response.json()

        if payload.get("retCode") != 0:
            raise BybitAPIError(
                f"Bybit retCode={payload.get('retCode')}: "
                f"{payload.get('retMsg', 'Unknown API error')}"
            )
        return payload.get("result", {})

    async def get_instruments_info(
        self,
        category: str = "linear",
        limit: int = 1000,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch instrument metadata, optionally narrowed to one symbol."""
        instruments: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            params: dict[str, Any] = {
                "category": category,
                "limit": min(max(limit, 1), 1000),
            }
            if symbol:
                params["symbol"] = symbol.upper()
            if cursor:
                params["cursor"] = cursor

            result = await self._get("/v5/market/instruments-info", params)
            instruments.extend(result.get("list", []))
            cursor = result.get("nextPageCursor") or None
            if not cursor:
                break

        return instruments

    async def get_klines(
        self,
        symbol: str,
        interval: str = "15",
        limit: int = 200,
        category: str = "linear",
    ) -> list[list[str]]:
        result = await self._get(
            "/v5/market/kline",
            {
                "category": category,
                "symbol": symbol.upper(),
                "interval": interval,
                "limit": min(max(limit, 1), 1000),
            },
        )
        return result.get("list", [])

    async def get_tickers(
        self,
        symbol: str | None = None,
        category: str = "linear",
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"category": category}
        if symbol:
            params["symbol"] = symbol.upper()
        result = await self._get("/v5/market/tickers", params)
        return result.get("list", [])

    async def get_server_time(self) -> dict[str, Any]:
        return await self._get("/v5/market/time", {})
