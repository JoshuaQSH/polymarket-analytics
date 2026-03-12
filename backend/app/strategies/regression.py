"""Linear-regression trend strategy for Polymarket events."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import numpy as np

from app.api.prices import fetch_price_history
from app.strategies.base import BaseStrategy, StrategyResult
from app.strategies.mean_reversion import (
    MINOR_INCIDENT_MAX_TRADERS,
    MINOR_INCIDENT_PROBABILITY_BAND,
    extract_price_history_market_id,
    is_minor_incident_event,
)

PriceHistoryFetcher = Callable[[str], Awaitable[list[dict[str, float | int]]]]


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


def _clean_prices(prices: Sequence[float]) -> list[float]:
    cleaned: list[float] = []
    for price in prices:
        parsed = _to_float(price)
        if parsed is None:
            continue
        if 0.0 <= parsed <= 1.0:
            cleaned.append(parsed)
    return cleaned


def _fit_trend(prices: Sequence[float]) -> tuple[float, float]:
    x = np.arange(len(prices), dtype=float)
    y = np.asarray(prices, dtype=float)
    design = np.column_stack([x, np.ones_like(x)])
    slope, intercept = np.linalg.lstsq(design, y, rcond=None)[0]
    return float(slope), float(intercept)


def _forecast_price(prices: Sequence[float], *, horizon: int) -> float:
    slope, intercept = _fit_trend(prices)
    future_x = len(prices) - 1 + horizon
    predicted = (slope * future_x) + intercept
    return float(np.clip(predicted, 0.0, 1.0))


def _build_rationale(
    signal: str,
    current_price: float,
    predicted_price: float,
    slope: float,
    edge_pct: float,
) -> str:
    if signal == "buy_yes":
        return (
            "Regression trend projects higher Yes probability "
            f"({current_price:.3f} -> {predicted_price:.3f}); "
            f"slope={slope:.4f}, edge={edge_pct:.2f}%."
        )
    if signal == "buy_no":
        return (
            "Regression trend projects lower Yes probability "
            f"({current_price:.3f} -> {predicted_price:.3f}); "
            f"slope={slope:.4f}, edge={edge_pct:.2f}%."
        )
    return (
        "Regression forecast is close to current Yes probability "
        f"({current_price:.3f} vs {predicted_price:.3f}); "
        f"slope={slope:.4f}, no directional edge."
    )


class RegressionTrendStrategy(BaseStrategy):
    """Trend-following strategy based on rolling linear regression forecasts."""

    def __init__(
        self,
        *,
        lookback_window: int = 12,
        forecast_horizon: int = 1,
        edge_threshold: float = 0.02,
        confidence_scale: float = 4.0,
        backtest_window: int = 60,
    ) -> None:
        self.lookback_window = lookback_window
        self.forecast_horizon = forecast_horizon
        self.edge_threshold = edge_threshold
        self.confidence_scale = confidence_scale
        self.backtest_window = backtest_window

    def evaluate(self, event_id: str, prices: Sequence[float]) -> StrategyResult:
        series = _clean_prices(prices)
        if len(series) < self.lookback_window + 1:
            return StrategyResult(
                event_id=event_id,
                signal="hold",
                confidence=0.0,
                expected_return_pct=0.0,
                rationale="Not enough price history for regression analysis.",
            )

        window = series[-self.lookback_window :]
        current_price = float(window[-1])
        predicted_price = _forecast_price(window, horizon=self.forecast_horizon)
        slope, _ = _fit_trend(window)
        edge = predicted_price - current_price
        edge_pct = edge * 100

        if edge >= self.edge_threshold:
            signal = "buy_yes"
            confidence = min(0.95, 0.55 + (abs(edge) * self.confidence_scale))
        elif edge <= -self.edge_threshold:
            signal = "buy_no"
            confidence = min(0.95, 0.55 + (abs(edge) * self.confidence_scale))
        else:
            signal = "hold"
            confidence = max(0.35, 0.55 - (abs(edge) * self.confidence_scale))

        expected_return_pct = self.estimate_expected_return_pct(series)
        rationale = _build_rationale(signal, current_price, predicted_price, slope, edge_pct)

        return StrategyResult(
            event_id=event_id,
            signal=signal,
            confidence=confidence,
            expected_return_pct=expected_return_pct,
            rationale=rationale,
        )

    def estimate_expected_return_pct(self, prices: Sequence[float]) -> float:
        series = _clean_prices(prices)
        if len(series) < self.lookback_window + 2:
            return 0.0

        windowed = series[-self.backtest_window :]
        simulated_returns: list[float] = []

        for index in range(self.lookback_window, len(windowed) - 1):
            history = windowed[index - self.lookback_window : index]
            current = windowed[index]
            next_price = windowed[index + 1]
            predicted = _forecast_price(history, horizon=self.forecast_horizon)
            edge = predicted - current

            if edge >= self.edge_threshold:
                if current <= 0:
                    continue
                simulated_returns.append((next_price - current) / current)
            elif edge <= -self.edge_threshold:
                no_price = 1 - current
                no_next = 1 - next_price
                if no_price <= 0:
                    continue
                simulated_returns.append((no_next - no_price) / no_price)

        if not simulated_returns:
            return 0.0

        return (sum(simulated_returns) / len(simulated_returns)) * 100


async def generate_regression_strategy_results(
    events: Sequence[dict[str, Any]],
    *,
    strategy: RegressionTrendStrategy | None = None,
    price_history_fetcher: PriceHistoryFetcher | None = None,
    max_traders: int = MINOR_INCIDENT_MAX_TRADERS,
    probability_band: float = MINOR_INCIDENT_PROBABILITY_BAND,
) -> list[dict[str, str | float]]:
    """Run regression-trend strategy for events matching minor-incident constraints."""
    active_strategy = strategy or RegressionTrendStrategy()

    async def _default_fetcher(market_id: str) -> list[dict[str, float | int]]:
        return await fetch_price_history(market_id, interval="1d")

    fetcher = price_history_fetcher or _default_fetcher

    results: list[dict[str, str | float]] = []
    for event in events:
        if not is_minor_incident_event(
            event,
            max_traders=max_traders,
            probability_band=probability_band,
        ):
            continue

        market_id = extract_price_history_market_id(event)
        if market_id is None:
            continue

        history = await fetcher(market_id)
        prices = [
            point["price"]
            for point in history
            if isinstance(point, dict) and _to_float(point.get("price")) is not None
        ]

        # Use higher-frequency fallback when daily history is too sparse.
        if price_history_fetcher is None and len(prices) < active_strategy.lookback_window + 1:
            hourly_history = await fetch_price_history(market_id, interval="1h")
            hourly_prices = [
                point["price"]
                for point in hourly_history
                if isinstance(point, dict) and _to_float(point.get("price")) is not None
            ]
            if len(hourly_prices) > len(prices):
                prices = hourly_prices

        result = active_strategy.evaluate(str(event.get("id", market_id)), prices)
        results.append(result.to_dict())

    return results

