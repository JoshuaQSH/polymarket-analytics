import pytest

from app.strategies.regression import (
    RegressionTrendStrategy,
    generate_regression_strategy_results,
)


def test_regression_returns_buy_yes_when_forecast_above_current() -> None:
    strategy = RegressionTrendStrategy(lookback_window=5, edge_threshold=0.01, forecast_horizon=1)
    prices = [0.30, 0.33, 0.36, 0.39, 0.42, 0.45]

    result = strategy.evaluate("evt-up", prices)

    assert result.signal == "buy_yes"
    assert result.confidence > 0.55


def test_regression_returns_buy_no_when_forecast_below_current() -> None:
    strategy = RegressionTrendStrategy(lookback_window=5, edge_threshold=0.01, forecast_horizon=1)
    prices = [0.70, 0.66, 0.62, 0.58, 0.54, 0.50]

    result = strategy.evaluate("evt-down", prices)

    assert result.signal == "buy_no"
    assert result.confidence > 0.55


def test_regression_returns_hold_when_edge_is_small() -> None:
    strategy = RegressionTrendStrategy(lookback_window=5, edge_threshold=0.05, forecast_horizon=1)
    prices = [0.49, 0.50, 0.51, 0.50, 0.49, 0.50]

    result = strategy.evaluate("evt-flat", prices)

    assert result.signal == "hold"


def test_regression_returns_hold_when_not_enough_history() -> None:
    strategy = RegressionTrendStrategy(lookback_window=6)

    result = strategy.evaluate("evt-short", [0.48, 0.49, 0.50])

    assert result.signal == "hold"
    assert result.confidence == 0.0
    assert result.expected_return_pct == 0.0


def test_regression_expected_return_is_numeric() -> None:
    strategy = RegressionTrendStrategy(lookback_window=5, edge_threshold=0.01, backtest_window=10)
    prices = [0.30, 0.32, 0.34, 0.36, 0.38, 0.40, 0.42, 0.44, 0.46, 0.48, 0.50]

    expected_return = strategy.estimate_expected_return_pct(prices)

    assert isinstance(expected_return, float)


@pytest.mark.asyncio
async def test_generate_regression_strategy_results_filters_events_and_runs_strategy() -> None:
    events = [
        {
            "id": "evt-1",
            "participantCount": 150,
            "yesProbability": 0.52,
            "conditionId": "cond-1",
            "markets": [{"clobTokenIds": ["token-1", "token-2"]}],
        },
        {"id": "evt-2", "participantCount": 700, "yesProbability": 0.51, "conditionId": "cond-2"},
        {"id": "evt-3", "participantCount": 150, "yesProbability": 0.85, "conditionId": "cond-3"},
        {"id": "evt-4", "participantCount": 150, "yesProbability": 0.51},
    ]

    async def fake_price_history_fetcher(market_id: str):
        assert market_id == "token-1"
        return [
            {"timestamp": 1, "price": 0.40},
            {"timestamp": 2, "price": 0.41},
            {"timestamp": 3, "price": 0.42},
            {"timestamp": 4, "price": 0.43},
            {"timestamp": 5, "price": 0.44},
            {"timestamp": 6, "price": 0.45},
            {"timestamp": 7, "price": 0.46},
            {"timestamp": 8, "price": 0.47},
            {"timestamp": 9, "price": 0.48},
            {"timestamp": 10, "price": 0.49},
            {"timestamp": 11, "price": 0.50},
            {"timestamp": 12, "price": 0.51},
            {"timestamp": 13, "price": 0.52},
        ]

    results = await generate_regression_strategy_results(
        events,
        price_history_fetcher=fake_price_history_fetcher,
    )

    assert len(results) == 1
    assert results[0]["event_id"] == "evt-1"
    assert results[0]["signal"] in {"buy_yes", "buy_no", "hold"}
    assert isinstance(results[0]["confidence"], float)
    assert isinstance(results[0]["expected_return_pct"], float)
