"""Price-history fetcher logic for Polymarket CLOB markets."""

from __future__ import annotations

from typing import Any, Iterable

from fastapi import APIRouter, HTTPException, Query

from app.services.clob_client import ClobClient, ClobClientError

router = APIRouter(prefix="/prices", tags=["prices"])


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _extract_timestamp(point: dict[str, Any]) -> int | None:
    for key in ("t", "timestamp", "time"):
        parsed = _to_float(point.get(key))
        if parsed is not None:
            return int(parsed)
    return None


def _extract_price(point: dict[str, Any]) -> float | None:
    for key in ("p", "price", "value"):
        parsed = _to_float(point.get(key))
        if parsed is not None:
            return parsed
    return None


def normalize_price_history(points: Iterable[dict[str, Any]]) -> list[dict[str, float | int]]:
    """Normalize CLOB price points to ``{\"timestamp\": int, \"price\": float}``."""
    normalized: list[dict[str, float | int]] = []

    for point in points:
        timestamp = _extract_timestamp(point)
        price = _extract_price(point)
        if timestamp is None or price is None:
            continue
        normalized.append({"timestamp": timestamp, "price": price})

    return sorted(normalized, key=lambda item: item["timestamp"])


async def fetch_price_history(
    condition_id: str,
    *,
    interval: str = "1d",
    clob_client: ClobClient | None = None,
) -> list[dict[str, float | int]]:
    """Fetch and normalize historical prices for a condition id."""
    if clob_client is not None:
        raw_history = await clob_client.get_price_history(condition_id, interval=interval)
        return normalize_price_history(raw_history)

    async with ClobClient() as client:
        raw_history = await client.get_price_history(condition_id, interval=interval)

    return normalize_price_history(raw_history)


@router.get("/{condition_id}")
async def get_price_history(
    condition_id: str,
    interval: str = Query(default="1d"),
) -> dict[str, Any]:
    """Return normalized price history for a given market condition id."""
    try:
        history = await fetch_price_history(condition_id, interval=interval)
    except ClobClientError as exc:
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch price history from CLOB",
        ) from exc

    return {
        "conditionId": condition_id,
        "interval": interval,
        "history": history,
    }
