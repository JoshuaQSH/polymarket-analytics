"""Async client for the Polymarket CLOB API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

LOGGER = logging.getLogger(__name__)
DEFAULT_CLOB_BASE_URL = "https://clob.polymarket.com"


class ClobClientError(RuntimeError):
    """Raised when CLOB API requests fail or return invalid payloads."""


class ClobClient:
    """Small async HTTP client wrapper for CLOB price history endpoints."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_CLOB_BASE_URL,
        timeout: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "ClobClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the internally-managed client, if any."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_price_history(
        self,
        condition_id: str,
        *,
        interval: str = "1d",
    ) -> list[dict[str, Any]]:
        payload = await self._get(
            "/prices-history",
            params={"market": condition_id, "interval": interval},
        )
        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            history = payload.get("history")
            if isinstance(history, list):
                return history

        raise ClobClientError(
            "Unexpected /prices-history response shape; expected list or {history: list}"
        )

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self._client

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        client = await self._ensure_client()
        try:
            response = await client.get(path, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            LOGGER.exception("CLOB request failed for %s", path)
            raise ClobClientError(f"CLOB request failed for {path}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise ClobClientError(f"CLOB returned non-JSON for {path}") from exc


async def fetch_price_history(
    condition_id: str,
    *,
    interval: str = "1d",
) -> list[dict[str, Any]]:
    """Convenience helper for one-shot price-history fetches."""
    async with ClobClient() as client:
        return await client.get_price_history(condition_id, interval=interval)
