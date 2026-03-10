"""Async client for the Polymarket Gamma API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

LOGGER = logging.getLogger(__name__)
DEFAULT_GAMMA_BASE_URL = "https://gamma-api.polymarket.com"


class GammaClientError(RuntimeError):
    """Raised when Gamma API requests fail or return invalid payloads."""


class GammaClient:
    """Small async HTTP client wrapper for Gamma event and market endpoints."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_GAMMA_BASE_URL,
        timeout: float = 15.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "GammaClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the internally-managed client, if any."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_events(
        self,
        *,
        limit: int = 100,
        order: str = "volume",
        ascending: bool = False,
    ) -> list[dict[str, Any]]:
        payload = await self._get(
            "/events",
            params={
                "limit": limit,
                "order": order,
                "ascending": ascending,
                "closed": False,
            },
        )
        if not isinstance(payload, list):
            raise GammaClientError("Unexpected /events response shape; expected a list")
        return payload

    async def get_markets(self, event_id: str | int) -> list[dict[str, Any]]:
        payload = await self._get("/markets", params={"event_id": str(event_id)})
        if not isinstance(payload, list):
            raise GammaClientError("Unexpected /markets response shape; expected a list")
        return payload

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
            LOGGER.exception("Gamma request failed for %s", path)
            raise GammaClientError(f"Gamma request failed for {path}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise GammaClientError(f"Gamma returned non-JSON for {path}") from exc


async def fetch_events(limit: int = 100) -> list[dict[str, Any]]:
    """Convenience helper for one-shot event fetches."""
    async with GammaClient() as client:
        return await client.get_events(limit=limit)


async def fetch_markets(event_id: str | int) -> list[dict[str, Any]]:
    """Convenience helper for one-shot market fetches."""
    async with GammaClient() as client:
        return await client.get_markets(event_id)
