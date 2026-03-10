"""Mean-reversion strategy baseline for Polymarket events."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from app.api.prices import fetch_price_history
from app.strategies.base import BaseStrategy, StrategyResult

MINOR_INCIDENT_MAX_TRADERS = 500
MINOR_INCIDENT_PROBABILITY_BAND = 0.15

PriceHistoryFetcher = Callable[[str], Awaitable[list[dict[str, float | int]]]]


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


def extract_participant_count(event: dict[str, Any]) -> int:
    for key in ("participantCount", "numTraders", "participants"):
        parsed = _to_float(event.get(key))
        if parsed is not None:
            return int(parsed)
    return 0


def extract_yes_probability(event: dict[str, Any]) -> float | None:
    for key in ("yesProbability", "probability", "bestBid", "bestAsk"):
        parsed = _to_float(event.get(key))
        if parsed is not None:
            return parsed

    outcome_prices = event.get("outcomePrices")
    outcomes = event.get("outcomes")

    if isinstance(outcome_prices, str):
        try:
            outcome_prices = json.loads(outcome_prices)
        except json.JSONDecodeError:
            outcome_prices = None

    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except json.JSONDecodeError:
            outcomes = None

    if isinstance(outcome_prices, list):
        if isinstance(outcomes, list):
            for idx, outcome in enumerate(outcomes):
                if (
                    isinstance(outcome, str)
                    and outcome.lower() == "yes"
                    and idx < len(outcome_prices)
                ):
                    parsed = _to_float(outcome_prices[idx])
                    if parsed is not None:
                        return parsed

        if outcome_prices:
            parsed = _to_float(outcome_prices[0])
            if parsed is not None:
                return parsed

    markets = event.get("markets")
    if isinstance(markets, list):
        for market in markets:
            if not isinstance(market, dict):
                continue
            parsed = extract_yes_probability(market)
            if parsed is not None:
                return parsed

    return None


def extract_condition_id(event: dict[str, Any]) -> str | None:
    for key in ("conditionId", "condition_id", "market", "marketId"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value

    markets = event.get("markets")
    if isinstance(markets, list):
        for market in markets:
            if not isinstance(market, dict):
                continue
            condition_id = market.get("conditionId") or market.get("condition_id")
            if isinstance(condition_id, str) and condition_id:
                return condition_id

    return None


def extract_price_history_market_id(event: dict[str, Any]) -> str | None:
    """Extract the best identifier for CLOB price-history queries."""
    for key in ("clobTokenId", "marketTokenId", "priceHistoryMarketId"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, str) and first:
                return first

    markets = event.get("markets")
    if isinstance(markets, list):
        for market in markets:
            if not isinstance(market, dict):
                continue

            clob_token_ids = market.get("clobTokenIds")
            if isinstance(clob_token_ids, str):
                try:
                    parsed_tokens = json.loads(clob_token_ids)
                except json.JSONDecodeError:
                    parsed_tokens = None
            elif isinstance(clob_token_ids, list):
                parsed_tokens = clob_token_ids
            else:
                parsed_tokens = None

            if isinstance(parsed_tokens, list) and parsed_tokens:
                first = parsed_tokens[0]
                if isinstance(first, str) and first:
                    return first

    return extract_condition_id(event)


def is_minor_incident_event(
    event: dict[str, Any],
    *,
    max_traders: int = MINOR_INCIDENT_MAX_TRADERS,
    probability_band: float = MINOR_INCIDENT_PROBABILITY_BAND,
) -> bool:
    participants = extract_participant_count(event)
    probability = extract_yes_probability(event)

    if probability is None:
        return False

    return participants < max_traders and abs(probability - 0.5) < probability_band


def _clean_prices(prices: Sequence[float]) -> list[float]:
    cleaned: list[float] = []
    for price in prices:
        parsed = _to_float(price)
        if parsed is None:
            continue
        # Polymarket probabilities should be within [0, 1].
        if 0.0 <= parsed <= 1.0:
            cleaned.append(parsed)
    return cleaned


def _build_rationale(signal: str, current_price: float, rolling_mean: float, deviation_pct: float) -> str:
    if signal == "buy_yes":
        return (
            "Current Yes price is below the 7-day mean by "
            f"{deviation_pct:.2f}%; reversion suggests upside in Yes."
        )
    if signal == "buy_no":
        return (
            "Current Yes price is above the 7-day mean by "
            f"{deviation_pct:.2f}%; reversion suggests upside in No."
        )
    return (
        "Current Yes price is near the 7-day mean "
        f"({current_price:.3f} vs {rolling_mean:.3f}); no strong mean-reversion edge."
    )


class MeanReversionStrategy(BaseStrategy):
    """Simple mean-reversion strategy with a 7-day baseline."""

    def __init__(
        self,
        *,
        lookback_window: int = 7,
        deviation_threshold: float = 0.10,
        backtest_window: int = 30,
    ) -> None:
        self.lookback_window = lookback_window
        self.deviation_threshold = deviation_threshold
        self.backtest_window = backtest_window

    def evaluate(self, event_id: str, prices: Sequence[float]) -> StrategyResult:
        series = _clean_prices(prices)
        if len(series) < self.lookback_window + 1:
            return StrategyResult(
                event_id=event_id,
                signal="hold",
                confidence=0.0,
                expected_return_pct=0.0,
                rationale="Not enough price history for mean-reversion analysis.",
            )

        rolling_slice = series[-self.lookback_window :]
        rolling_mean = sum(rolling_slice) / len(rolling_slice)
        current_price = series[-1]

        if rolling_mean <= 0:
            return StrategyResult(
                event_id=event_id,
                signal="hold",
                confidence=0.0,
                expected_return_pct=0.0,
                rationale="Invalid rolling mean from price history.",
            )

        deviation = (current_price - rolling_mean) / rolling_mean
        deviation_pct = abs(deviation) * 100

        if deviation <= -self.deviation_threshold:
            signal = "buy_yes"
            confidence = min(0.95, 0.55 + abs(deviation))
        elif deviation >= self.deviation_threshold:
            signal = "buy_no"
            confidence = min(0.95, 0.55 + abs(deviation))
        else:
            signal = "hold"
            confidence = max(0.35, 0.55 - abs(deviation))

        expected_return_pct = self.estimate_expected_return_pct(series)
        rationale = _build_rationale(signal, current_price, rolling_mean, deviation_pct)

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
            mean_price = sum(windowed[index - self.lookback_window : index]) / self.lookback_window
            if mean_price <= 0:
                continue

            current = windowed[index]
            next_price = windowed[index + 1]
            deviation = (current - mean_price) / mean_price

            if deviation <= -self.deviation_threshold:
                if current <= 0:
                    continue
                simulated_returns.append((next_price - current) / current)
            elif deviation >= self.deviation_threshold:
                no_price = 1 - current
                no_next = 1 - next_price
                if no_price <= 0:
                    continue
                simulated_returns.append((no_next - no_price) / no_price)

        if not simulated_returns:
            return 0.0

        return (sum(simulated_returns) / len(simulated_returns)) * 100


async def generate_strategy_results(
    events: Sequence[dict[str, Any]],
    *,
    strategy: MeanReversionStrategy | None = None,
    price_history_fetcher: PriceHistoryFetcher | None = None,
) -> list[dict[str, str | float]]:
    """Run mean-reversion strategy for events matching minor-incident constraints."""
    active_strategy = strategy or MeanReversionStrategy()

    async def _default_fetcher(market_id: str) -> list[dict[str, float | int]]:
        return await fetch_price_history(market_id, interval="1d")

    fetcher = price_history_fetcher or _default_fetcher

    results: list[dict[str, str | float]] = []
    for event in events:
        if not is_minor_incident_event(event):
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

        # For thin/new markets, daily candles can be sparse. Fallback to hourly
        # history so the strategy can still evaluate runtime data.
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
