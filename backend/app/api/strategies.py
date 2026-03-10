"""Strategy API routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.events import fetch_events
from app.services.clob_client import ClobClientError
from app.services.gamma_client import GammaClientError
from app.strategies.llm_strategy import (
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_REMOTE_MODEL,
    LlmInferenceError,
    generate_llm_strategy_results,
)
from app.strategies.mean_reversion import generate_strategy_results

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("")
async def list_strategies(
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[dict[str, str | float]]:
    """Generate mean-reversion strategy outputs for candidate events."""
    try:
        events: list[dict[str, Any]] = await fetch_events(limit=limit)
    except GammaClientError as exc:
        raise HTTPException(status_code=502, detail="Failed to fetch events from Gamma") from exc

    try:
        return await generate_strategy_results(events)
    except ClobClientError as exc:
        raise HTTPException(status_code=502, detail="Failed to fetch price history from CLOB") from exc


class StrategySimulationRequest(BaseModel):
    strategy_type: Literal["mean_reversion", "llm"] = "mean_reversion"
    limit: int = Field(default=100, ge=1, le=500)
    interval_seconds: int = Field(default=60, ge=5, le=3600)
    provider: Literal["local", "remote", "claude"] = "local"
    model: str | None = None
    api_key: str | None = None
    llm_max_events: int = Field(default=5, ge=1, le=50)
    use_cache: bool = True


class StrategySimulationResponse(BaseModel):
    strategy_type: Literal["mean_reversion", "llm"]
    provider: Literal["local", "remote", "claude"] | None = None
    model: str | None = None
    interval_seconds: int
    executed_at: str
    next_run_at: str
    earnings_rate_pct: float
    results: list[dict[str, Any]]


def _compute_earnings_rate(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0

    rates: list[float] = []
    for row in results:
        direct_rate = row.get("earnings_rate_pct")
        if isinstance(direct_rate, (float, int)):
            rates.append(float(direct_rate))
            continue

        confidence = row.get("confidence")
        expected = row.get("expected_return_pct")
        if isinstance(confidence, (float, int)) and isinstance(expected, (float, int)):
            rates.append(float(confidence) * float(expected))

    if not rates:
        return 0.0
    return round(sum(rates) / len(rates), 4)


@router.post("/simulate", response_model=StrategySimulationResponse)
async def simulate_strategies(payload: StrategySimulationRequest) -> StrategySimulationResponse:
    """
    Execute one simulation pass and return scheduling metadata for polling.

    The frontend can re-trigger this endpoint every ``interval_seconds`` for a
    timed simulation loop.
    """
    try:
        events: list[dict[str, Any]] = await fetch_events(limit=payload.limit)
    except GammaClientError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch events from Gamma: {exc}",
        ) from exc

    resolved_model: str | None = None
    provider: Literal["local", "remote", "claude"] | None = None

    try:
        if payload.strategy_type == "llm":
            provider = payload.provider
            if payload.model:
                resolved_model = payload.model
            elif provider == "local":
                resolved_model = DEFAULT_LOCAL_MODEL
            elif provider == "claude":
                resolved_model = DEFAULT_CLAUDE_MODEL
            else:
                resolved_model = DEFAULT_REMOTE_MODEL
            results = await generate_llm_strategy_results(
                events,
                provider=provider,
                model=resolved_model,
                api_key=payload.api_key,
                max_events=payload.llm_max_events,
                use_cache=payload.use_cache,
            )
        else:
            results = await generate_strategy_results(events)
    except ClobClientError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch price history from CLOB: {exc}",
        ) from exc
    except LlmInferenceError as exc:
        raise HTTPException(status_code=502, detail=f"LLM strategy failed: {exc}") from exc

    now = datetime.now(UTC)
    next_run = now + timedelta(seconds=payload.interval_seconds)

    return StrategySimulationResponse(
        strategy_type=payload.strategy_type,
        provider=provider,
        model=resolved_model,
        interval_seconds=payload.interval_seconds,
        executed_at=now.isoformat(),
        next_run_at=next_run.isoformat(),
        earnings_rate_pct=_compute_earnings_rate(results),
        results=results,
    )
