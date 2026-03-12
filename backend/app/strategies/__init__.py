"""Strategy engines and helpers."""

from app.strategies.base import BaseStrategy, StrategyResult
from app.strategies.mean_reversion import (
    MeanReversionStrategy,
    extract_condition_id,
    generate_strategy_results,
    is_minor_incident_event,
)
from app.strategies.regression import (
    RegressionTrendStrategy,
    generate_regression_strategy_results,
)
from app.strategies.llm_strategy import (
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_REMOTE_MODEL,
    LlmInferenceError,
    build_analysis_prompt,
    generate_llm_strategy_results,
    infer_claude_model,
    infer_local_model,
    infer_remote_model,
    infer_with_cache,
    parse_llm_strategy_content,
)

__all__ = [
    "BaseStrategy",
    "StrategyResult",
    "MeanReversionStrategy",
    "RegressionTrendStrategy",
    "extract_condition_id",
    "generate_strategy_results",
    "generate_regression_strategy_results",
    "is_minor_incident_event",
    "DEFAULT_CLAUDE_MODEL",
    "DEFAULT_LOCAL_MODEL",
    "DEFAULT_REMOTE_MODEL",
    "LlmInferenceError",
    "build_analysis_prompt",
    "generate_llm_strategy_results",
    "infer_claude_model",
    "infer_local_model",
    "infer_remote_model",
    "infer_with_cache",
    "parse_llm_strategy_content",
]
