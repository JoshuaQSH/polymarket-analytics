"""LLM fine-tuning dataset export utilities."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.api.events import fetch_events
from app.api.prices import normalize_price_history
from app.strategies.mean_reversion import (
    extract_price_history_market_id,
    generate_strategy_results,
)
from app.strategies.base import StrategyResult

DEFAULT_SYSTEM_PROMPT = "You are a prediction market analyst."
DEFAULT_EXPORT_DIR = Path(__file__).resolve().parents[2] / "data" / "finetune"

EventsFetcher = Callable[[int], Awaitable[list[dict[str, Any]]]]
StrategiesFetcher = Callable[[Sequence[dict[str, Any]]], Awaitable[list[dict[str, Any]]]]
PriceHistoryFetcher = Callable[[str], Awaitable[list[dict[str, float | int]]]]


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _extract_tags(event: dict[str, Any]) -> list[str]:
    raw_tags = event.get("tags")
    if raw_tags is None:
        return []

    tags: list[str] = []

    if isinstance(raw_tags, str):
        return [raw_tags] if raw_tags else []

    if not isinstance(raw_tags, list):
        return []

    for item in raw_tags:
        if isinstance(item, str) and item:
            tags.append(item)
            continue

        if isinstance(item, dict):
            for key in ("name", "label", "slug"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    tags.append(value)
                    break

    return tags


def _extract_volume(event: dict[str, Any]) -> float | None:
    for key in ("volume", "volume24hr", "volume24H", "liquidity", "openInterest"):
        parsed = _as_float(event.get(key))
        if parsed is not None:
            return parsed
    return None


def _extract_title(event: dict[str, Any]) -> str:
    for key in ("title", "question", "name"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    return f"Event {event.get('id', 'unknown')}"


def _extract_description(event: dict[str, Any]) -> str:
    for key in ("description", "subtitle", "details"):
        value = event.get(key)
        if isinstance(value, str):
            return value
    return ""


def build_event_payload(
    event: dict[str, Any],
    *,
    price_history: Sequence[dict[str, Any]],
    market_id: str | None = None,
) -> dict[str, Any]:
    """Build compact event payload for fine-tuning prompts."""
    normalized_history = normalize_price_history(price_history)[-30:]

    return {
        "event_id": str(event.get("id", "")),
        "market_id": market_id or extract_price_history_market_id(event),
        "title": _extract_title(event),
        "description": _extract_description(event),
        "num_traders": int(_as_float(event.get("participantCount") or event.get("numTraders") or 0) or 0),
        "volume": _extract_volume(event),
        "yes_probability": _as_float(event.get("yesProbability")),
        "tags": _extract_tags(event),
        "probability_history_30d": normalized_history,
    }


def build_assistant_payload(strategy_result: dict[str, Any]) -> dict[str, Any]:
    """Return canonical assistant output payload."""
    return {
        "event_id": str(strategy_result.get("event_id", "")),
        "signal": str(strategy_result.get("signal", "hold")),
        "confidence": float(_as_float(strategy_result.get("confidence")) or 0.0),
        "expected_return_pct": float(
            _as_float(strategy_result.get("expected_return_pct")) or 0.0
        ),
        "rationale": str(strategy_result.get("rationale", "")),
    }


def build_finetune_record(
    event: dict[str, Any],
    strategy_result: dict[str, Any] | StrategyResult,
    *,
    price_history: Sequence[dict[str, Any]],
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    market_id: str | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Build one JSONL record in HF SFT messages format."""
    if isinstance(strategy_result, StrategyResult):
        strategy_payload = strategy_result.to_dict()
    else:
        strategy_payload = dict(strategy_result)

    event_payload = build_event_payload(
        event,
        price_history=price_history,
        market_id=market_id,
    )
    assistant_payload = build_assistant_payload(strategy_payload)

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Analyze this Polymarket event and propose a trading action:\n"
                    f"{json.dumps(event_payload, separators=(',', ':'))}"
                ),
            },
            {
                "role": "assistant",
                "content": json.dumps(assistant_payload, separators=(",", ":")),
            },
        ]
    }


def write_jsonl(
    records: Sequence[dict[str, Any]],
    *,
    output_dir: str | Path = DEFAULT_EXPORT_DIR,
    as_of: date | None = None,
) -> Path:
    """Write records to ``events_YYYYMMDD.jsonl`` and return file path."""
    target_date = as_of or datetime.now(timezone.utc).date()
    output_path = Path(output_dir) / f"events_{target_date.strftime('%Y%m%d')}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True))
            handle.write("\n")

    return output_path


async def export_live_finetune_dataset(
    *,
    limit: int = 100,
    output_dir: str | Path = DEFAULT_EXPORT_DIR,
    as_of: date | None = None,
    events_fetcher: EventsFetcher | None = None,
    strategies_fetcher: StrategiesFetcher | None = None,
    price_history_fetcher: PriceHistoryFetcher | None = None,
) -> Path:
    """
    Export a live fine-tuning dataset from current event + strategy snapshots.

    The exporter matches strategy results to events by ``event_id`` and includes
    up to the most recent 30 normalized price points per market.
    """
    active_events_fetcher = events_fetcher or (lambda limit_value: fetch_events(limit=limit_value))
    active_strategies_fetcher = strategies_fetcher or generate_strategy_results

    async def _default_price_fetcher(market_id: str) -> list[dict[str, float | int]]:
        from app.api.prices import fetch_price_history  # lazy import avoids cycles

        return await fetch_price_history(market_id, interval="1d")

    active_price_fetcher = price_history_fetcher or _default_price_fetcher

    events = await active_events_fetcher(limit)
    strategies = await active_strategies_fetcher(events)
    events_by_id = {str(event.get("id", "")): event for event in events}

    records: list[dict[str, Any]] = []

    for strategy in strategies:
        event_id = str(strategy.get("event_id", ""))
        event = events_by_id.get(event_id)
        if event is None:
            continue

        market_id = extract_price_history_market_id(event)
        history: list[dict[str, float | int]] = []
        if market_id:
            history = await active_price_fetcher(market_id)

        records.append(
            build_finetune_record(
                event,
                strategy,
                price_history=history,
                market_id=market_id,
            )
        )

    return write_jsonl(records, output_dir=output_dir, as_of=as_of)
