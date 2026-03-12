import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

import { StrategyTable } from "../components/StrategyTable";
import { useStrategySimulation } from "../hooks/useStrategySimulation";

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

const LOCAL_MODEL_OPTIONS = ["tinyllama", "qwen2.5:3b", "llama3.2:3b"] as const;
const REMOTE_MODEL_OPTIONS = ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1-nano"] as const;
const CLAUDE_MODEL_OPTIONS = [
  "claude-3-5-haiku-latest",
  "claude-3-5-sonnet-latest",
  "claude-3-7-sonnet-latest",
] as const;
const LLM_EVENT_OPTIONS = [1, 3, 5, 10, 20] as const;

export function StrategyPage() {
  const {
    config,
    setConfig,
    autoRunEnabled,
    setAutoRunEnabled,
    runOnce,
    countdownSeconds,
    strategies,
    simulation,
    isLoading,
    error,
    summary,
  } = useStrategySimulation();

  const bankrollUsd = 1_000;
  const allocationPct = 10;

  const projectedPortfolioReturnUsd = strategies.reduce((sum, strategy) => {
    const tradeUsd = bankrollUsd * (allocationPct / 100);
    const estimate = tradeUsd * strategy.confidence * (strategy.expected_return_pct / 100);
    return sum + estimate;
  }, 0);

  const projectedPortfolioReturnPct = bankrollUsd > 0 ? (projectedPortfolioReturnUsd / bankrollUsd) * 100 : 0;

  const confidenceAdjustedEdge = clamp(
    summary.avgExpectedReturnPct * summary.weightedConfidence,
    -100,
    100
  );
  const hasRunInitialRef = useRef(false);

  useEffect(() => {
    if (hasRunInitialRef.current) {
      return;
    }
    hasRunInitialRef.current = true;
    void runOnce();
  }, [runOnce]);

  const strategyTitle =
    config.strategyType === "llm"
      ? "LLM Strategy Simulation"
      : config.strategyType === "regression"
        ? "Regression Trend Signals"
        : "Mean-Reversion Signals";
  const modelOptions =
    config.provider === "remote"
      ? REMOTE_MODEL_OPTIONS
      : config.provider === "claude"
        ? CLAUDE_MODEL_OPTIONS
        : LOCAL_MODEL_OPTIONS;

  return (
    <main className="page page--strategies">
      <section className="hero">
        <Link className="detail-header__back" to="/">
          Back to Event Radar
        </Link>
        <p className="hero__eyebrow">Strategy Engine</p>
        <h1 className="hero__title">{strategyTitle}</h1>
        <p className="hero__subtitle">
          Run deterministic mean-reversion or LLM-guided simulation on a recurring interval. The backend
          receives the same interval and returns next-run timestamps for synchronized polling.
        </p>

        <section className="simulation-controls" aria-label="Strategy simulation controls">
          <div className="simulation-controls__grid">
            <label>
              Strategy
              <select
                value={config.strategyType}
                onChange={(event) =>
                  setConfig((prev) => ({
                    ...prev,
                    strategyType: event.target.value as "mean_reversion" | "regression" | "llm",
                    model:
                      event.target.value === "llm"
                        ? prev.provider === "remote"
                          ? REMOTE_MODEL_OPTIONS[0]
                          : prev.provider === "claude"
                            ? CLAUDE_MODEL_OPTIONS[0]
                          : LOCAL_MODEL_OPTIONS[0]
                        : prev.model,
                  }))
                }
              >
                <option value="mean_reversion">Mean Reversion</option>
                <option value="regression">Regression Trend</option>
                <option value="llm">LLM Strategy</option>
              </select>
            </label>

            <label>
              Refresh (seconds)
              <input
                type="number"
                min={5}
                max={3600}
                value={config.intervalSeconds}
                onChange={(event) =>
                  setConfig((prev) => ({
                    ...prev,
                    intervalSeconds: Number(event.target.value) || 60,
                  }))
                }
              />
            </label>

            <label>
              Event limit
              <input
                type="number"
                min={1}
                max={500}
                value={config.limit}
                onChange={(event) =>
                  setConfig((prev) => ({
                    ...prev,
                    limit: Number(event.target.value) || 100,
                  }))
                }
              />
            </label>
          </div>

          {config.strategyType === "llm" && (
            <div className="simulation-controls__grid">
              <label>
                LLM Provider
                <select
                  value={config.provider}
                  onChange={(event) =>
                    setConfig((prev) => ({
                      ...prev,
                      provider: event.target.value as "local" | "remote" | "claude",
                      model:
                        event.target.value === "remote"
                          ? REMOTE_MODEL_OPTIONS[0]
                          : event.target.value === "claude"
                            ? CLAUDE_MODEL_OPTIONS[0]
                          : LOCAL_MODEL_OPTIONS[0],
                    }))
                  }
                >
                  <option value="local">Local</option>
                  <option value="remote">OpenAI API</option>
                  <option value="claude">Claude API</option>
                </select>
              </label>

              <label>
                Model
                <select
                  value={config.model}
                  onChange={(event) =>
                    setConfig((prev) => ({
                      ...prev,
                      model: event.target.value,
                    }))
                  }
                >
                  {modelOptions.map((modelOption) => (
                    <option key={modelOption} value={modelOption}>
                      {modelOption}
                    </option>
                  ))}
                </select>
              </label>

              {config.provider !== "local" && (
                <label>
                  API Key ({config.provider === "claude" ? "Anthropic" : "OpenAI"})
                  <input
                    type="password"
                    value={config.apiKey}
                    onChange={(event) =>
                      setConfig((prev) => ({
                        ...prev,
                        apiKey: event.target.value,
                      }))
                    }
                    placeholder={
                      config.provider === "claude"
                        ? "anthropic-api-key"
                        : "sk-proj-..."
                    }
                  />
                </label>
              )}

              <label>
                LLM Events / run
                <select
                  value={config.llmMaxEvents}
                  onChange={(event) =>
                    setConfig((prev) => ({
                      ...prev,
                      llmMaxEvents: Number(event.target.value) || 5,
                    }))
                  }
                >
                  {LLM_EVENT_OPTIONS.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}

          <div className="simulation-controls__actions">
            <button type="button" className="hero__cta hero__cta--button" onClick={() => void runOnce()}>
              Run Once
            </button>
            <button
              type="button"
              className="hero__cta hero__cta--button"
              onClick={() => setAutoRunEnabled((prev) => !prev)}
            >
              {autoRunEnabled ? "Stop Auto Run" : "Start Auto Run"}
            </button>
            {config.strategyType === "llm" && (
              <label className="simulation-controls__checkbox">
                <input
                  type="checkbox"
                  checked={config.useCache}
                  onChange={(event) =>
                    setConfig((prev) => ({
                      ...prev,
                      useCache: event.target.checked,
                    }))
                  }
                />
                Use backend LLM cache
              </label>
            )}
            <Link className="hero__cta" to="/strategy-benefits">
              Open Benefit Comparison
            </Link>
          </div>
        </section>

        <div className="stats-grid stats-grid--strategies">
          <article className="stat-card">
            <p>Total Signals</p>
            <strong>{summary.total}</strong>
          </article>
          <article className="stat-card">
            <p>Buy Yes / Buy No / Hold</p>
            <strong>
              {summary.buyYes} / {summary.buyNo} / {summary.hold}
            </strong>
          </article>
          <article className="stat-card">
            <p>Avg Expected Return</p>
            <strong>{summary.avgExpectedReturnPct.toFixed(2)}%</strong>
          </article>
          <article className="stat-card">
            <p>Confidence-Adjusted Edge</p>
            <strong>{confidenceAdjustedEdge.toFixed(2)}%</strong>
          </article>
          <article className="stat-card">
            <p>Avg Earnings Rate</p>
            <strong>{summary.avgEarningsRatePct.toFixed(2)}%</strong>
          </article>
        </div>
      </section>

      <section className="estimator-panel" aria-label="Return estimator">
        <h2>Return Estimator</h2>
        <p>
          Assumptions: ${bankrollUsd.toLocaleString()} bankroll, {allocationPct}% allocation per signal,
          expected return weighted by strategy confidence.
        </p>

        <div className="estimator-metrics">
          <div>
            <span>Projected PnL</span>
            <strong>${projectedPortfolioReturnUsd.toFixed(2)}</strong>
          </div>
          <div>
            <span>Projected Return</span>
            <strong>{projectedPortfolioReturnPct.toFixed(2)}%</strong>
          </div>
          <div>
            <span>Backend Interval</span>
            <strong>{simulation?.interval_seconds ?? config.intervalSeconds}s</strong>
          </div>
          <div>
            <span>Earnings Rate</span>
            <strong>{(simulation?.earnings_rate_pct ?? summary.avgEarningsRatePct).toFixed(2)}%</strong>
          </div>
          <div>
            <span>Last Run (UTC)</span>
            <strong className="mono">
              {simulation?.executed_at ? new Date(simulation.executed_at).toISOString() : "-"}
            </strong>
          </div>
          <div>
            <span>Next Run In</span>
            <strong>{countdownSeconds === null ? "-" : `${countdownSeconds}s`}</strong>
          </div>
        </div>
      </section>

      {isLoading && <p className="state-message">Loading strategy results...</p>}
      {error && <p className="state-message state-message--error">{error}</p>}

      {!isLoading && !error && strategies.length > 0 && (
        <StrategyTable
          strategies={strategies}
          bankrollUsd={bankrollUsd}
          allocationPct={allocationPct}
        />
      )}

      {!isLoading && !error && strategies.length === 0 && (
        <p className="state-message">No strategy results were generated for the current event set.</p>
      )}
    </main>
  );
}
