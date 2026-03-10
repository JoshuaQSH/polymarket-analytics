from fastapi.testclient import TestClient

from app.main import app
from app.services.clob_client import ClobClientError
from app.services.gamma_client import GammaClientError
from app.strategies.llm_strategy import LlmInferenceError

client = TestClient(app)


def test_health_route_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_events_route_returns_ranked_events(monkeypatch) -> None:
    async def fake_fetch_ranked_events(**kwargs):
        assert kwargs["limit"] == 50
        return [{"id": "evt-1", "participantCount": 12, "isNearFiftyProbability": True}]

    monkeypatch.setattr("app.api.events.fetch_ranked_events", fake_fetch_ranked_events)

    response = client.get("/events", params={"limit": 50})

    assert response.status_code == 200
    assert response.json() == [{"id": "evt-1", "participantCount": 12, "isNearFiftyProbability": True}]


def test_event_detail_route_returns_not_found(monkeypatch) -> None:
    async def fake_fetch_ranked_events(**kwargs):
        return [{"id": "evt-1"}, {"id": "evt-2"}]

    monkeypatch.setattr("app.api.events.fetch_ranked_events", fake_fetch_ranked_events)

    response = client.get("/events/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Event missing not found"


def test_event_detail_route_maps_gamma_errors_to_502(monkeypatch) -> None:
    async def fake_fetch_ranked_events(**kwargs):
        raise GammaClientError("boom")

    monkeypatch.setattr("app.api.events.fetch_ranked_events", fake_fetch_ranked_events)

    response = client.get("/events/evt-1")

    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to fetch events from Gamma"


def test_prices_route_returns_normalized_history(monkeypatch) -> None:
    async def fake_fetch_price_history(condition_id: str, *, interval: str = "1d", clob_client=None):
        assert condition_id == "cond-1"
        assert interval == "1h"
        return [{"timestamp": 1, "price": 0.48}, {"timestamp": 2, "price": 0.52}]

    monkeypatch.setattr("app.api.prices.fetch_price_history", fake_fetch_price_history)

    response = client.get("/prices/cond-1", params={"interval": "1h"})

    assert response.status_code == 200
    assert response.json() == {
        "conditionId": "cond-1",
        "interval": "1h",
        "history": [{"timestamp": 1, "price": 0.48}, {"timestamp": 2, "price": 0.52}],
    }


def test_prices_route_maps_clob_errors_to_502(monkeypatch) -> None:
    async def fake_fetch_price_history(condition_id: str, *, interval: str = "1d", clob_client=None):
        raise ClobClientError("boom")

    monkeypatch.setattr("app.api.prices.fetch_price_history", fake_fetch_price_history)

    response = client.get("/prices/cond-1")

    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to fetch price history from CLOB"


def test_strategies_route_returns_results(monkeypatch) -> None:
    async def fake_fetch_events(*, limit: int = 100, gamma_client=None):
        assert limit == 25
        return [{"id": "evt-1"}]

    async def fake_generate_strategy_results(events, *, strategy=None, price_history_fetcher=None):
        assert events == [{"id": "evt-1"}]
        return [
            {
                "event_id": "evt-1",
                "signal": "hold",
                "confidence": 0.55,
                "expected_return_pct": 1.25,
                "rationale": "test rationale",
            }
        ]

    monkeypatch.setattr("app.api.strategies.fetch_events", fake_fetch_events)
    monkeypatch.setattr(
        "app.api.strategies.generate_strategy_results",
        fake_generate_strategy_results,
    )

    response = client.get("/strategies", params={"limit": 25})

    assert response.status_code == 200
    assert response.json()[0]["event_id"] == "evt-1"


def test_strategies_route_maps_gamma_errors_to_502(monkeypatch) -> None:
    async def fake_fetch_events(*, limit: int = 100, gamma_client=None):
        raise GammaClientError("boom")

    monkeypatch.setattr("app.api.strategies.fetch_events", fake_fetch_events)

    response = client.get("/strategies")

    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to fetch events from Gamma"


def test_strategies_route_maps_clob_errors_to_502(monkeypatch) -> None:
    async def fake_fetch_events(*, limit: int = 100, gamma_client=None):
        return [{"id": "evt-1"}]

    async def fake_generate_strategy_results(events, *, strategy=None, price_history_fetcher=None):
        raise ClobClientError("boom")

    monkeypatch.setattr("app.api.strategies.fetch_events", fake_fetch_events)
    monkeypatch.setattr(
        "app.api.strategies.generate_strategy_results",
        fake_generate_strategy_results,
    )

    response = client.get("/strategies")

    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to fetch price history from CLOB"


def test_simulate_strategies_route_returns_mean_reversion_payload(monkeypatch) -> None:
    async def fake_fetch_events(*, limit: int = 100, gamma_client=None):
        assert limit == 25
        return [{"id": "evt-1"}]

    async def fake_generate_strategy_results(events, *, strategy=None, price_history_fetcher=None):
        assert events == [{"id": "evt-1"}]
        return [
            {
                "event_id": "evt-1",
                "signal": "hold",
                "confidence": 0.6,
                "expected_return_pct": 2.0,
                "earnings_rate_pct": 1.2,
                "rationale": "test",
            }
        ]

    monkeypatch.setattr("app.api.strategies.fetch_events", fake_fetch_events)
    monkeypatch.setattr(
        "app.api.strategies.generate_strategy_results",
        fake_generate_strategy_results,
    )

    response = client.post(
        "/strategies/simulate",
        json={"strategy_type": "mean_reversion", "limit": 25, "interval_seconds": 45},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_type"] == "mean_reversion"
    assert payload["interval_seconds"] == 45
    assert payload["earnings_rate_pct"] == 1.2
    assert payload["provider"] is None
    assert payload["results"][0]["event_id"] == "evt-1"


def test_simulate_strategies_route_runs_llm_strategy(monkeypatch) -> None:
    async def fake_fetch_events(*, limit: int = 100, gamma_client=None):
        assert limit == 10
        return [{"id": "evt-2"}]

    async def fake_generate_llm_strategy_results(
        events,
        *,
        provider="local",
        model=None,
        api_key=None,
        max_events=20,
        price_history_fetcher=None,
        llm_inferer=None,
        use_cache=True,
    ):
        assert provider == "remote"
        assert model == "gpt-4o-mini"
        assert api_key == "test-key"
        assert max_events == 3
        return [
            {
                "event_id": "evt-2",
                "signal": "buy_yes",
                "confidence": 0.7,
                "expected_return_pct": 4.0,
                "earnings_rate_pct": 2.8,
                "rationale": "llm",
                "provider": "remote",
                "model": "gpt-4o-mini",
            }
        ]

    monkeypatch.setattr("app.api.strategies.fetch_events", fake_fetch_events)
    monkeypatch.setattr(
        "app.api.strategies.generate_llm_strategy_results",
        fake_generate_llm_strategy_results,
    )

    response = client.post(
        "/strategies/simulate",
        json={
            "strategy_type": "llm",
            "provider": "remote",
            "model": "gpt-4o-mini",
            "api_key": "test-key",
            "llm_max_events": 3,
            "limit": 10,
            "interval_seconds": 30,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_type"] == "llm"
    assert payload["provider"] == "remote"
    assert payload["model"] == "gpt-4o-mini"
    assert payload["earnings_rate_pct"] == 2.8
    assert payload["results"][0]["signal"] == "buy_yes"


def test_simulate_strategies_route_maps_llm_errors_to_502(monkeypatch) -> None:
    async def fake_fetch_events(*, limit: int = 100, gamma_client=None):
        return [{"id": "evt-2"}]

    async def fake_generate_llm_strategy_results(
        events,
        *,
        provider="local",
        model=None,
        api_key=None,
        max_events=20,
        price_history_fetcher=None,
        llm_inferer=None,
        use_cache=True,
    ):
        raise LlmInferenceError("Remote LLM inference request failed")

    monkeypatch.setattr("app.api.strategies.fetch_events", fake_fetch_events)
    monkeypatch.setattr(
        "app.api.strategies.generate_llm_strategy_results",
        fake_generate_llm_strategy_results,
    )

    response = client.post(
        "/strategies/simulate",
        json={"strategy_type": "llm", "provider": "remote", "interval_seconds": 30},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "LLM strategy failed: Remote LLM inference request failed"


def test_llm_local_infer_route_returns_response(monkeypatch) -> None:
    async def fake_infer_with_cache(
        prompt: str,
        *,
        provider: str,
        model: str,
        ttl_seconds: int = 3600,
        cache_path=None,
        api_key=None,
        base_url=None,
        client=None,
    ):
        assert prompt == "hello"
        assert provider == "local"
        assert model == "tinyllama"
        return "local result", False

    monkeypatch.setattr("app.api.llm_strategy.infer_with_cache", fake_infer_with_cache)

    response = client.post("/llm/infer/local", json={"prompt": "hello"})

    assert response.status_code == 200
    assert response.json() == {
        "provider": "local",
        "model": "tinyllama",
        "content": "local result",
        "cached": False,
    }


def test_llm_remote_infer_route_maps_errors_to_502(monkeypatch) -> None:
    async def fake_infer_with_cache(
        prompt: str,
        *,
        provider: str,
        model: str,
        ttl_seconds: int = 3600,
        cache_path=None,
        api_key=None,
        base_url=None,
        client=None,
    ):
        raise LlmInferenceError("Remote LLM inference request failed")

    monkeypatch.setattr("app.api.llm_strategy.infer_with_cache", fake_infer_with_cache)

    response = client.post("/llm/infer/remote", json={"prompt": "hello", "api_key": "abc"})

    assert response.status_code == 502
    assert response.json()["detail"] == "Remote LLM inference request failed"


def test_llm_claude_infer_route_returns_response(monkeypatch) -> None:
    async def fake_infer_with_cache(
        prompt: str,
        *,
        provider: str,
        model: str,
        ttl_seconds: int = 3600,
        cache_path=None,
        api_key=None,
        base_url=None,
        client=None,
    ):
        assert prompt == "hello"
        assert provider == "claude"
        assert model == "claude-3-5-haiku-latest"
        assert api_key == "claude-key"
        return "claude result", False

    monkeypatch.setattr("app.api.llm_strategy.infer_with_cache", fake_infer_with_cache)

    response = client.post(
        "/llm/infer/claude",
        json={"prompt": "hello", "api_key": "claude-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "provider": "claude",
        "model": "claude-3-5-haiku-latest",
        "content": "claude result",
        "cached": False,
    }
