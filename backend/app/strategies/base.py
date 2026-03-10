"""Base abstractions for strategy engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Sequence

SignalType = Literal["buy_yes", "buy_no", "hold"]


@dataclass(slots=True)
class StrategyResult:
    """Canonical strategy output payload."""

    event_id: str
    signal: SignalType
    confidence: float
    expected_return_pct: float
    rationale: str

    def to_dict(self) -> dict[str, str | float]:
        return {
            "event_id": self.event_id,
            "signal": self.signal,
            "confidence": round(self.confidence, 4),
            "expected_return_pct": round(self.expected_return_pct, 4),
            "rationale": self.rationale,
        }


class BaseStrategy(ABC):
    """Abstract strategy interface."""

    @abstractmethod
    def evaluate(self, event_id: str, prices: Sequence[float]) -> StrategyResult:
        """Generate a strategy recommendation for an event."""
