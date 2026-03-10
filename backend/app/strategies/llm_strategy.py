"""Local and remote LLM inference helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx

from app.api.prices import fetch_price_history
from app.strategies.mean_reversion import (
    MeanReversionStrategy,
    extract_price_history_market_id,
    extract_yes_probability,
    is_minor_incident_event,
)

DEFAULT_LOCAL_BASE_URL = "http://localhost:11434"
DEFAULT_LOCAL_MODEL = "tinyllama"
DEFAULT_REMOTE_BASE_URL = "https://api.openai.com/v1"
DEFAULT_REMOTE_MODEL = "gpt-4o-mini"
DEFAULT_CLAUDE_BASE_URL = "https://api.anthropic.com/v1"
DEFAULT_CLAUDE_MODEL = "claude-3-5-haiku-latest"
DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "cache" / "llm_results.json"
MINOR_INCIDENT_MAX_LLM_EVENTS = 20

LlmProvider = Literal["local", "remote", "claude"]
PriceHistoryFetcher = Callable[[str], Awaitable[list[dict[str, float | int]]]]
LlmInferer = Callable[[str], Awaitable[str]]


class LlmInferenceError(RuntimeError):
    """Raised when an LLM inference call fails."""


def _to_float(value: Any) -> float | None:
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


def _clamp(value: float, *, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def build_analysis_prompt(event_payload: dict[str, Any]) -> str:
    """Build an analysis prompt from a structured event payload."""
    return (
        "You are a prediction-market analyst. Return concise JSON with keys "
        "signal, confidence, expected_return_pct, rationale.\n\n"
        f"Event payload:\n{json.dumps(event_payload, ensure_ascii=True)}"
    )


def parse_llm_strategy_content(content: str) -> dict[str, str | float]:
    """
    Parse model output into canonical strategy fields.

    Falls back to ``hold`` with zeroed metrics when parsing fails.
    """
    payload: Any = None
    try:
        payload = json.loads(content)
    except ValueError:
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            try:
                payload = json.loads(match.group(0))
            except ValueError:
                payload = None

    if not isinstance(payload, dict):
        return {
            "signal": "hold",
            "confidence": 0.0,
            "expected_return_pct": 0.0,
            "rationale": "",
        }

    raw_signal = payload.get("signal")
    if isinstance(raw_signal, str):
        normalized = raw_signal.strip().lower().replace(" ", "_")
    else:
        normalized = "hold"

    if normalized in {"buy", "buy_yes", "yes", "long_yes", "long"}:
        signal = "buy_yes"
    elif normalized in {"sell", "buy_no", "no", "short_no", "short"}:
        signal = "buy_no"
    else:
        signal = "hold"

    confidence = _to_float(payload.get("confidence"))
    if confidence is None:
        confidence = 0.0
    if confidence > 1.0 and confidence <= 100.0:
        confidence = confidence / 100.0
    confidence = _clamp(confidence, min_value=0.0, max_value=1.0)

    expected_return_pct = _to_float(payload.get("expected_return_pct"))
    if expected_return_pct is None:
        expected_return_pct = 0.0

    rationale = payload.get("rationale")
    if not isinstance(rationale, str):
        rationale = ""

    return {
        "signal": signal,
        "confidence": confidence,
        "expected_return_pct": expected_return_pct,
        "rationale": rationale.strip(),
    }


def _hash_prompt(prompt: str, *, provider: str, model: str) -> str:
    digest = hashlib.sha256(f"{provider}:{model}:{prompt}".encode("utf-8")).hexdigest()
    return digest


def _load_cache(path: Path = DEFAULT_CACHE_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}

    if not isinstance(payload, dict):
        return {}
    return {str(k): v for k, v in payload.items() if isinstance(v, dict)}


def _save_cache(cache: dict[str, dict[str, Any]], path: Path = DEFAULT_CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=True, indent=2), encoding="utf-8")


def get_cached_response(
    prompt: str,
    *,
    provider: str,
    model: str,
    ttl_seconds: int = 3600,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> str | None:
    key = _hash_prompt(prompt, provider=provider, model=model)
    cache = _load_cache(cache_path)
    entry = cache.get(key)
    if entry is None:
        return None

    created_at = entry.get("created_at")
    content = entry.get("content")
    if not isinstance(created_at, str) or not isinstance(content, str):
        return None

    try:
        created_dt = datetime.fromisoformat(created_at)
    except ValueError:
        return None

    age_seconds = (datetime.now(UTC) - created_dt).total_seconds()
    if age_seconds > ttl_seconds:
        return None

    return content


def cache_response(
    prompt: str,
    *,
    provider: str,
    model: str,
    content: str,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> None:
    key = _hash_prompt(prompt, provider=provider, model=model)
    cache = _load_cache(cache_path)
    cache[key] = {
        "provider": provider,
        "model": model,
        "content": content,
        "created_at": datetime.now(UTC).isoformat(),
    }
    _save_cache(cache, cache_path)


async def infer_local_model(
    prompt: str,
    *,
    model: str = DEFAULT_LOCAL_MODEL,
    base_url: str = DEFAULT_LOCAL_BASE_URL,
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Run inference against an Ollama-compatible local endpoint."""
    payload = {"model": model, "prompt": prompt, "stream": False}
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=timeout)

    try:
        response = await active_client.post(f"{base_url.rstrip('/')}/api/generate", json=payload)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:240]
        raise LlmInferenceError(
            f"Local LLM inference request failed ({exc.response.status_code}): {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise LlmInferenceError(f"Local LLM inference request failed: {exc}") from exc
    finally:
        if owns_client:
            await active_client.aclose()

    body = response.json()
    if not isinstance(body, dict):
        raise LlmInferenceError("Local LLM response was not a JSON object")

    content = body.get("response")
    if not isinstance(content, str) or not content:
        raise LlmInferenceError("Local LLM response missing 'response' text")

    return content


async def infer_remote_model(
    prompt: str,
    *,
    model: str = DEFAULT_REMOTE_MODEL,
    api_key: str | None = None,
    base_url: str = DEFAULT_REMOTE_BASE_URL,
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Run inference against an OpenAI-compatible remote endpoint."""
    resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved_api_key:
        raise LlmInferenceError("Missing API key for remote inference")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {resolved_api_key}"}
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=timeout)

    try:
        response = await active_client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:240]
        raise LlmInferenceError(
            f"Remote LLM inference request failed ({exc.response.status_code}): {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise LlmInferenceError(f"Remote LLM inference request failed: {exc}") from exc
    finally:
        if owns_client:
            await active_client.aclose()

    body = response.json()
    if not isinstance(body, dict):
        raise LlmInferenceError("Remote LLM response was not a JSON object")

    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LlmInferenceError("Remote LLM response missing choices")

    first = choices[0]
    if not isinstance(first, dict):
        raise LlmInferenceError("Remote LLM response choice had invalid shape")

    message = first.get("message")
    if not isinstance(message, dict):
        raise LlmInferenceError("Remote LLM response missing message object")

    content = message.get("content")
    if not isinstance(content, str) or not content:
        raise LlmInferenceError("Remote LLM response missing message content")

    return content


async def infer_claude_model(
    prompt: str,
    *,
    model: str = DEFAULT_CLAUDE_MODEL,
    api_key: str | None = None,
    base_url: str = DEFAULT_CLAUDE_BASE_URL,
    timeout: float = 30.0,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Run inference against the Anthropic Messages API."""
    resolved_api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    if not resolved_api_key:
        raise LlmInferenceError("Missing API key for Claude inference")

    payload = {
        "model": model,
        "max_tokens": 300,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": resolved_api_key,
        "anthropic-version": "2023-06-01",
    }
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=timeout)

    try:
        response = await active_client.post(
            f"{base_url.rstrip('/')}/messages",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:240]
        raise LlmInferenceError(
            f"Claude inference request failed ({exc.response.status_code}): {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise LlmInferenceError(f"Claude inference request failed: {exc}") from exc
    finally:
        if owns_client:
            await active_client.aclose()

    body = response.json()
    if not isinstance(body, dict):
        raise LlmInferenceError("Claude response was not a JSON object")

    content_blocks = body.get("content")
    if not isinstance(content_blocks, list) or not content_blocks:
        raise LlmInferenceError("Claude response missing content blocks")

    texts: list[str] = []
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text:
            texts.append(text)

    if not texts:
        raise LlmInferenceError("Claude response missing text content")

    return "\n".join(texts).strip()


async def infer_with_cache(
    prompt: str,
    *,
    provider: str,
    model: str,
    ttl_seconds: int = 3600,
    cache_path: Path = DEFAULT_CACHE_PATH,
    api_key: str | None = None,
    base_url: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[str, bool]:
    """
    Infer with cache lookup.

    Returns ``(content, from_cache)``.
    """
    cached = get_cached_response(
        prompt,
        provider=provider,
        model=model,
        ttl_seconds=ttl_seconds,
        cache_path=cache_path,
    )
    if cached is not None:
        return cached, True

    if provider == "local":
        content = await infer_local_model(
            prompt,
            model=model,
            base_url=base_url or DEFAULT_LOCAL_BASE_URL,
            client=client,
        )
    elif provider == "remote":
        content = await infer_remote_model(
            prompt,
            model=model,
            api_key=api_key,
            base_url=base_url or DEFAULT_REMOTE_BASE_URL,
            client=client,
        )
    elif provider == "claude":
        content = await infer_claude_model(
            prompt,
            model=model,
            api_key=api_key,
            base_url=base_url or DEFAULT_CLAUDE_BASE_URL,
            client=client,
        )
    else:
        raise LlmInferenceError(f"Unsupported provider: {provider}")

    cache_response(
        prompt,
        provider=provider,
        model=model,
        content=content,
        cache_path=cache_path,
    )
    return content, False


async def generate_llm_strategy_results(
    events: Sequence[dict[str, Any]],
    *,
    provider: LlmProvider = "local",
    model: str | None = None,
    api_key: str | None = None,
    max_events: int = MINOR_INCIDENT_MAX_LLM_EVENTS,
    price_history_fetcher: PriceHistoryFetcher | None = None,
    llm_inferer: LlmInferer | None = None,
    use_cache: bool = True,
) -> list[dict[str, str | float]]:
    """
    Generate strategy outputs using LLM inference over minor-incident events.

    This mirrors the mean-reversion pipeline but lets the model choose the
    signal/confidence/expected return from structured event context.
    """
    if model:
        resolved_model = model
    elif provider == "local":
        resolved_model = DEFAULT_LOCAL_MODEL
    elif provider == "claude":
        resolved_model = DEFAULT_CLAUDE_MODEL
    else:
        resolved_model = DEFAULT_REMOTE_MODEL
    baseline_strategy = MeanReversionStrategy()

    async def _default_price_fetcher(market_id: str) -> list[dict[str, float | int]]:
        return await fetch_price_history(market_id, interval="1d")

    async def _default_inferer(prompt: str) -> str:
        content, _ = await infer_with_cache(
            prompt,
            provider=provider,
            model=resolved_model,
            api_key=api_key,
            ttl_seconds=3600 if use_cache else 0,
        )
        return content

    fetcher = price_history_fetcher or _default_price_fetcher
    inferer = llm_inferer or _default_inferer

    results: list[dict[str, str | float]] = []
    seen = 0
    for event in events:
        if seen >= max_events:
            break
        if not is_minor_incident_event(event):
            continue

        market_id = extract_price_history_market_id(event)
        if market_id is None:
            continue

        history = await fetcher(market_id)
        prices = [
            float(point["price"])
            for point in history
            if isinstance(point, dict) and _to_float(point.get("price")) is not None
        ]

        if price_history_fetcher is None and len(prices) < baseline_strategy.lookback_window + 1:
            hourly_history = await fetch_price_history(market_id, interval="1h")
            hourly_prices = [
                float(point["price"])
                for point in hourly_history
                if isinstance(point, dict) and _to_float(point.get("price")) is not None
            ]
            if len(hourly_prices) > len(prices):
                prices = hourly_prices

        event_id = str(event.get("id", market_id))
        baseline = baseline_strategy.evaluate(event_id, prices)

        prompt_payload = {
            "event_id": event_id,
            "title": event.get("title") or event.get("question") or event_id,
            "participants": event.get("participantCount") or event.get("numTraders") or 0,
            "yes_probability": extract_yes_probability(event),
            "latest_yes_price": prices[-1] if prices else None,
            "price_points": len(prices),
            "baseline_signal": baseline.signal,
            "baseline_expected_return_pct": baseline.expected_return_pct,
            "baseline_rationale": baseline.rationale,
        }
        prompt = build_analysis_prompt(prompt_payload)
        raw = await inferer(prompt)
        parsed = parse_llm_strategy_content(raw)

        parsed_confidence = _to_float(parsed.get("confidence"))
        confidence = parsed_confidence if parsed_confidence is not None else baseline.confidence
        confidence = _clamp(confidence, min_value=0.0, max_value=1.0)

        parsed_expected = _to_float(parsed.get("expected_return_pct"))
        expected_return_pct = (
            parsed_expected if parsed_expected is not None else baseline.expected_return_pct
        )

        parsed_signal = parsed.get("signal")
        signal = parsed_signal if parsed_signal in {"buy_yes", "buy_no", "hold"} else baseline.signal

        parsed_rationale = parsed.get("rationale")
        rationale = (
            str(parsed_rationale).strip()
            if isinstance(parsed_rationale, str) and parsed_rationale.strip()
            else baseline.rationale
        )

        earnings_rate_pct = confidence * expected_return_pct
        results.append(
            {
                "event_id": event_id,
                "signal": signal,
                "confidence": round(confidence, 4),
                "expected_return_pct": round(expected_return_pct, 4),
                "earnings_rate_pct": round(earnings_rate_pct, 4),
                "rationale": rationale,
                "provider": provider,
                "model": resolved_model,
            }
        )
        seen += 1

    return results
