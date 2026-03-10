"""Event-fetching and ranking logic for Polymarket events."""

from __future__ import annotations

import json
from typing import Any, Iterable

from fastapi import APIRouter, HTTPException, Query

from app.services.gamma_client import GammaClient, GammaClientError

DEFAULT_NEAR_FIFTY_THRESHOLD = 0.10
DEFAULT_MINOR_INCIDENT_MAX_TRADERS = 500

router = APIRouter(prefix="/events", tags=["events"])


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


def _extract_num_traders(event: dict[str, Any]) -> int:
    for key in ("numTraders", "participants", "participantCount"):
        parsed = _to_float(event.get(key))
        if parsed is not None:
            return int(parsed)
    return 0


def _extract_probability_from_outcomes(event: dict[str, Any]) -> float | None:
    prices = event.get("outcomePrices")
    outcomes = event.get("outcomes")

    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except json.JSONDecodeError:
            prices = None

    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except json.JSONDecodeError:
            outcomes = None

    if isinstance(prices, list):
        if isinstance(outcomes, list):
            for idx, outcome in enumerate(outcomes):
                if isinstance(outcome, str) and outcome.lower() == "yes" and idx < len(prices):
                    return _to_float(prices[idx])

        if prices:
            return _to_float(prices[0])

    markets = event.get("markets")
    if not isinstance(markets, list):
        return None

    for market in markets:
        if not isinstance(market, dict):
            continue

        market_prices = market.get("outcomePrices")
        market_outcomes = market.get("outcomes")

        if isinstance(market_prices, str):
            try:
                market_prices = json.loads(market_prices)
            except json.JSONDecodeError:
                market_prices = None

        if isinstance(market_outcomes, str):
            try:
                market_outcomes = json.loads(market_outcomes)
            except json.JSONDecodeError:
                market_outcomes = None

        if not isinstance(market_prices, list):
            continue

        if isinstance(market_outcomes, list):
            for idx, outcome in enumerate(market_outcomes):
                if (
                    isinstance(outcome, str)
                    and outcome.lower() == "yes"
                    and idx < len(market_prices)
                ):
                    parsed = _to_float(market_prices[idx])
                    if parsed is not None:
                        return parsed

        if market_prices:
            parsed = _to_float(market_prices[0])
            if parsed is not None:
                return parsed

    return None


def extract_yes_probability(event: dict[str, Any]) -> float | None:
    """Attempt to extract YES probability from common Gamma event fields."""
    for field in ("yesProbability", "probability", "bestBid", "bestAsk"):
        parsed = _to_float(event.get(field))
        if parsed is not None:
            return parsed

    return _extract_probability_from_outcomes(event)


def rank_events(
    events: Iterable[dict[str, Any]],
    *,
    near_fifty_threshold: float = DEFAULT_NEAR_FIFTY_THRESHOLD,
    minor_incident_max_traders: int | None = DEFAULT_MINOR_INCIDENT_MAX_TRADERS,
) -> list[dict[str, Any]]:
    """
    Rank events by participant count descending, then near-50 probability.

    Returns shallow copies annotated with:
    - ``participantCount`` (int)
    - ``yesProbability`` (float | None)
    - ``isNearFiftyProbability`` (bool)
    """
    ranked_input: list[dict[str, Any]] = []

    for event in events:
        participant_count = _extract_num_traders(event)
        if (
            minor_incident_max_traders is not None
            and participant_count > minor_incident_max_traders
        ):
            continue

        yes_probability = extract_yes_probability(event)
        is_near_fifty = (
            yes_probability is not None
            and abs(yes_probability - 0.5) <= near_fifty_threshold
        )

        enriched = dict(event)
        enriched["participantCount"] = participant_count
        enriched["yesProbability"] = yes_probability
        enriched["isNearFiftyProbability"] = is_near_fifty
        ranked_input.append(enriched)

    return sorted(
        ranked_input,
        key=lambda event: (
            -event["participantCount"],
            -int(event["isNearFiftyProbability"]),
        ),
    )


async def fetch_events(
    *,
    limit: int = 100,
    gamma_client: GammaClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch raw events from Gamma using an injected or managed client."""
    if gamma_client is not None:
        return await gamma_client.get_events(limit=limit)

    async with GammaClient() as client:
        return await client.get_events(limit=limit)


async def fetch_ranked_events(
    *,
    limit: int = 100,
    gamma_client: GammaClient | None = None,
    near_fifty_threshold: float = DEFAULT_NEAR_FIFTY_THRESHOLD,
    minor_incident_max_traders: int | None = DEFAULT_MINOR_INCIDENT_MAX_TRADERS,
) -> list[dict[str, Any]]:
    """Fetch events from Gamma and apply participant/probability ranking."""
    events = await fetch_events(limit=limit, gamma_client=gamma_client)
    return rank_events(
        events,
        near_fifty_threshold=near_fifty_threshold,
        minor_incident_max_traders=minor_incident_max_traders,
    )


@router.get("")
async def list_events(
    limit: int = Query(default=100, ge=1, le=1000),
    near_fifty_threshold: float = Query(default=DEFAULT_NEAR_FIFTY_THRESHOLD, ge=0.0, le=0.5),
    minor_incident_max_traders: int | None = Query(default=DEFAULT_MINOR_INCIDENT_MAX_TRADERS, ge=0),
) -> list[dict[str, Any]]:
    """Return ranked events for the frontend list page."""
    try:
        return await fetch_ranked_events(
            limit=limit,
            near_fifty_threshold=near_fifty_threshold,
            minor_incident_max_traders=minor_incident_max_traders,
        )
    except GammaClientError as exc:
        raise HTTPException(status_code=502, detail="Failed to fetch events from Gamma") from exc


@router.get("/{event_id}")
async def get_event(
    event_id: str,
    limit: int = Query(default=1000, ge=1, le=5000),
) -> dict[str, Any]:
    """Return one event by id from the fetched event set."""
    try:
        events = await fetch_ranked_events(
            limit=limit,
            minor_incident_max_traders=None,
        )
    except GammaClientError as exc:
        raise HTTPException(status_code=502, detail="Failed to fetch events from Gamma") from exc

    for event in events:
        if str(event.get("id")) == str(event_id):
            return event

    raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
