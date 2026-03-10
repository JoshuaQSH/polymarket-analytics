import httpx
import pytest
import respx

from app.strategies.llm_strategy import (
    LlmInferenceError,
    build_analysis_prompt,
    generate_llm_strategy_results,
    infer_claude_model,
    infer_local_model,
    infer_remote_model,
    infer_with_cache,
    parse_llm_strategy_content,
)


def test_build_analysis_prompt_includes_payload() -> None:
    prompt = build_analysis_prompt({"event_id": "evt-1", "title": "Test"})
    assert "event_id" in prompt
    assert "evt-1" in prompt


@pytest.mark.asyncio
@respx.mock
async def test_infer_local_model_success() -> None:
    route = respx.post("http://localhost:11434/api/generate").mock(
        return_value=httpx.Response(200, json={"response": '{"signal":"hold"}'})
    )

    result = await infer_local_model("hello")

    assert route.called
    assert result == '{"signal":"hold"}'


@pytest.mark.asyncio
@respx.mock
async def test_infer_remote_model_success() -> None:
    route = respx.post("https://api.openai.com/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"signal":"buy_yes"}'}}]},
        )
    )

    result = await infer_remote_model("prompt", api_key="test-key")

    assert route.called
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer test-key"
    assert result == '{"signal":"buy_yes"}'


@pytest.mark.asyncio
@respx.mock
async def test_infer_claude_model_success() -> None:
    route = respx.post("https://api.anthropic.com/v1/messages").mock(
        return_value=httpx.Response(
            200,
            json={"content": [{"type": "text", "text": '{"signal":"hold"}'}]},
        )
    )

    result = await infer_claude_model("prompt", api_key="claude-key")

    assert route.called
    request = route.calls[0].request
    assert request.headers["x-api-key"] == "claude-key"
    assert result == '{"signal":"hold"}'


@pytest.mark.asyncio
async def test_infer_remote_model_requires_api_key() -> None:
    with pytest.raises(LlmInferenceError, match="Missing API key"):
        await infer_remote_model("prompt", api_key=None)


@pytest.mark.asyncio
async def test_infer_claude_model_requires_api_key() -> None:
    with pytest.raises(LlmInferenceError, match="Missing API key"):
        await infer_claude_model("prompt", api_key=None)


@pytest.mark.asyncio
@respx.mock
async def test_infer_with_cache_returns_cached_result(tmp_path) -> None:
    route = respx.post("http://localhost:11434/api/generate").mock(
        return_value=httpx.Response(200, json={"response": "cached text"})
    )
    cache_path = tmp_path / "llm_results.json"

    first, from_cache_first = await infer_with_cache(
        "prompt",
        provider="local",
        model="tinyllama",
        cache_path=cache_path,
    )
    second, from_cache_second = await infer_with_cache(
        "prompt",
        provider="local",
        model="tinyllama",
        cache_path=cache_path,
    )

    assert first == "cached text"
    assert from_cache_first is False
    assert second == "cached text"
    assert from_cache_second is True
    assert route.call_count == 1


def test_parse_llm_strategy_content_handles_json_and_fallback_text() -> None:
    parsed = parse_llm_strategy_content('{"signal":"buy_yes","confidence":72,"expected_return_pct":3.5}')
    assert parsed["signal"] == "buy_yes"
    assert parsed["confidence"] == 0.72
    assert parsed["expected_return_pct"] == 3.5

    fallback = parse_llm_strategy_content("no json here")
    assert fallback["signal"] == "hold"
    assert fallback["confidence"] == 0.0


@pytest.mark.asyncio
async def test_generate_llm_strategy_results_returns_earnings_rate() -> None:
    events = [
        {
            "id": "evt-1",
            "participantCount": 120,
            "yesProbability": 0.51,
            "markets": [{"clobTokenIds": ["token-1"]}],
        }
    ]

    async def fake_price_history_fetcher(market_id: str):
        assert market_id == "token-1"
        return [
            {"timestamp": 1, "price": 0.5},
            {"timestamp": 2, "price": 0.49},
            {"timestamp": 3, "price": 0.51},
            {"timestamp": 4, "price": 0.5},
            {"timestamp": 5, "price": 0.49},
            {"timestamp": 6, "price": 0.5},
            {"timestamp": 7, "price": 0.48},
            {"timestamp": 8, "price": 0.47},
        ]

    async def fake_llm_inferer(prompt: str) -> str:
        assert "event_id" in prompt
        return '{"signal":"buy_no","confidence":0.8,"expected_return_pct":5.0,"rationale":"llm edge"}'

    results = await generate_llm_strategy_results(
        events,
        provider="remote",
        model="gpt-4o-mini",
        api_key="test-key",
        price_history_fetcher=fake_price_history_fetcher,
        llm_inferer=fake_llm_inferer,
    )

    assert len(results) == 1
    assert results[0]["event_id"] == "evt-1"
    assert results[0]["signal"] == "buy_no"
    assert results[0]["confidence"] == 0.8
    assert results[0]["expected_return_pct"] == 5.0
    assert results[0]["earnings_rate_pct"] == 4.0
