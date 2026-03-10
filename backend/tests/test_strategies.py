import pytest

from app.strategies.mean_reversion import (
    MeanReversionStrategy,
    extract_condition_id,
    extract_price_history_market_id,
    generate_strategy_results,
    is_minor_incident_event,
)


def test_mean_reversion_returns_buy_yes_when_price_far_below_mean() -> None:
    strategy = MeanReversionStrategy(lookback_window=7, deviation_threshold=0.10)
    prices = [0.50, 0.52, 0.49, 0.51, 0.50, 0.52, 0.50, 0.35]

    result = strategy.evaluate("evt-1", prices)

    assert result.signal == "buy_yes"
    assert result.confidence > 0.6


def test_mean_reversion_returns_buy_no_when_price_far_above_mean() -> None:
    strategy = MeanReversionStrategy(lookback_window=7, deviation_threshold=0.10)
    prices = [0.50, 0.48, 0.49, 0.51, 0.50, 0.49, 0.50, 0.70]

    result = strategy.evaluate("evt-2", prices)

    assert result.signal == "buy_no"
    assert result.confidence > 0.6


def test_mean_reversion_returns_hold_when_within_threshold() -> None:
    strategy = MeanReversionStrategy(lookback_window=7, deviation_threshold=0.10)
    prices = [0.50, 0.48, 0.49, 0.51, 0.50, 0.49, 0.50, 0.53]

    result = strategy.evaluate("evt-3", prices)

    assert result.signal == "hold"


def test_is_minor_incident_event_applies_filters() -> None:
    assert (
        is_minor_incident_event(
            {"participantCount": 100, "yesProbability": 0.51},
        )
        is True
    )
    assert (
        is_minor_incident_event(
            {"participantCount": 700, "yesProbability": 0.51},
        )
        is False
    )
    assert (
        is_minor_incident_event(
            {"participantCount": 100, "yesProbability": 0.81},
        )
        is False
    )


def test_extract_condition_id_reads_top_level_and_markets() -> None:
    assert extract_condition_id({"conditionId": "cond-top"}) == "cond-top"
    assert extract_condition_id({"markets": [{"conditionId": "cond-market"}]}) == "cond-market"


def test_extract_price_history_market_id_prefers_clob_token_ids() -> None:
    event = {
        "conditionId": "cond-top",
        "markets": [{"clobTokenIds": '["token-yes","token-no"]', "conditionId": "cond-market"}],
    }

    assert extract_price_history_market_id(event) == "token-yes"


def test_is_minor_incident_event_reads_nested_market_probability() -> None:
    event = {
        "participantCount": 120,
        "markets": [
            {
                "outcomes": '["Yes", "No"]',
                "outcomePrices": '["0.49", "0.51"]',
            }
        ],
    }

    assert is_minor_incident_event(event) is True


@pytest.mark.asyncio
async def test_generate_strategy_results_filters_events_and_runs_strategy() -> None:
    events = [
        {
            "id": "evt-1",
            "participantCount": 150,
            "yesProbability": 0.52,
            "conditionId": "cond-1",
            "markets": [{"clobTokenIds": ["token-1", "token-2"]}],
        },
        {"id": "evt-2", "participantCount": 800, "yesProbability": 0.51, "conditionId": "cond-2"},
        {"id": "evt-3", "participantCount": 150, "yesProbability": 0.85, "conditionId": "cond-3"},
        {"id": "evt-4", "participantCount": 150, "yesProbability": 0.51},
    ]

    async def fake_price_history_fetcher(market_id: str):
        assert market_id == "token-1"
        return [
            {"timestamp": 1, "price": 0.51},
            {"timestamp": 2, "price": 0.50},
            {"timestamp": 3, "price": 0.49},
            {"timestamp": 4, "price": 0.50},
            {"timestamp": 5, "price": 0.48},
            {"timestamp": 6, "price": 0.49},
            {"timestamp": 7, "price": 0.50},
            {"timestamp": 8, "price": 0.40},
        ]

    results = await generate_strategy_results(
        events,
        price_history_fetcher=fake_price_history_fetcher,
    )

    assert len(results) == 1
    assert results[0]["event_id"] == "evt-1"
    assert results[0]["signal"] in {"buy_yes", "buy_no", "hold"}
    assert isinstance(results[0]["confidence"], float)
    assert isinstance(results[0]["expected_return_pct"], float)
