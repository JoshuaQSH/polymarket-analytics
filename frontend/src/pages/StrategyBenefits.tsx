import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { StrategyResult, simulateStrategies } from "../api/client";

type QuantStrategyType = "mean_reversion" | "regression";

type StrategyBenefitPoint = {
  strategyType: QuantStrategyType;
  strategyLabel: string;
  earningsRatePct: number;
  avgExpectedReturnPct: number;
  signalCount: number;
  buyYes: number;
  buyNo: number;
  hold: number;
  executedAt: string;
};

const QUANT_STRATEGIES: Array<{ type: QuantStrategyType; label: string }> = [
  { type: "mean_reversion", label: "Mean Reversion" },
  { type: "regression", label: "Regression Trend" },
];

function summarizeSignals(results: StrategyResult[]) {
  const buyYes = results.filter((result) => result.signal === "buy_yes").length;
  const buyNo = results.filter((result) => result.signal === "buy_no").length;
  const hold = results.filter((result) => result.signal === "hold").length;

  return { buyYes, buyNo, hold };
}

export function StrategyBenefitsPage() {
  const [limit, setLimit] = useState(100);
  const [intervalSeconds, setIntervalSeconds] = useState(60);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<StrategyBenefitPoint[]>([]);

  const runComparison = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    const settled = await Promise.allSettled(
      QUANT_STRATEGIES.map(async (strategy) => {
        const response = await simulateStrategies({
          strategy_type: strategy.type,
          limit,
          interval_seconds: intervalSeconds,
          provider: "local",
          model: "tinyllama",
        });

        const signalSummary = summarizeSignals(response.results);
        const avgExpectedReturnPct =
          response.results.length > 0
            ? response.results.reduce((sum, row) => sum + row.expected_return_pct, 0) /
              response.results.length
            : 0;

        return {
          strategyType: strategy.type,
          strategyLabel: strategy.label,
          earningsRatePct: response.earnings_rate_pct,
          avgExpectedReturnPct,
          signalCount: response.results.length,
          buyYes: signalSummary.buyYes,
          buyNo: signalSummary.buyNo,
          hold: signalSummary.hold,
          executedAt: response.executed_at,
        } satisfies StrategyBenefitPoint;
      })
    );

    const successful: StrategyBenefitPoint[] = [];
    const errors: string[] = [];

    for (let index = 0; index < settled.length; index += 1) {
      const outcome = settled[index];
      if (outcome.status === "fulfilled") {
        successful.push(outcome.value);
      } else {
        const strategyLabel = QUANT_STRATEGIES[index]?.label ?? "Unknown Strategy";
        const reason = outcome.reason instanceof Error ? outcome.reason.message : String(outcome.reason);
        errors.push(`${strategyLabel}: ${reason}`);
      }
    }

    setData(successful);
    setIsLoading(false);
    setError(errors.length > 0 ? errors.join(" | ") : null);
  }, [intervalSeconds, limit]);

  useEffect(() => {
    void runComparison();
  }, [runComparison]);

  const bestStrategy = useMemo(() => {
    if (data.length === 0) {
      return null;
    }
    return [...data].sort((left, right) => right.earningsRatePct - left.earningsRatePct)[0];
  }, [data]);

  return (
    <main className="page page--strategy-benefits">
      <section className="hero">
        <Link className="detail-header__back" to="/strategies">
          Back to Strategy Engine
        </Link>
        <p className="hero__eyebrow">Strategy Comparison</p>
        <h1 className="hero__title">Benefit Rate Plot</h1>
        <p className="hero__subtitle">
          Compare earnings rate and expected return across all quantitative strategies on the same event
          universe.
        </p>
      </section>

      <section className="simulation-controls" aria-label="Benefit comparison controls">
        <div className="simulation-controls__grid">
          <label>
            Event limit
            <input
              type="number"
              min={1}
              max={500}
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value) || 100)}
            />
          </label>
          <label>
            Backend interval (seconds)
            <input
              type="number"
              min={5}
              max={3600}
              value={intervalSeconds}
              onChange={(event) => setIntervalSeconds(Number(event.target.value) || 60)}
            />
          </label>
        </div>
        <div className="simulation-controls__actions">
          <button
            type="button"
            className="hero__cta hero__cta--button"
            onClick={() => void runComparison()}
          >
            Refresh Comparison
          </button>
        </div>
      </section>

      <div className="stats-grid stats-grid--strategies">
        <article className="stat-card">
          <p>Strategies Compared</p>
          <strong>{data.length}</strong>
        </article>
        <article className="stat-card">
          <p>Best Earnings Rate</p>
          <strong>{bestStrategy ? `${bestStrategy.earningsRatePct.toFixed(2)}%` : "-"}</strong>
        </article>
        <article className="stat-card">
          <p>Top Strategy</p>
          <strong>{bestStrategy?.strategyLabel ?? "-"}</strong>
        </article>
      </div>

      <section className="chart-panel benefits-panel" aria-label="Strategy benefit chart">
        <div className="chart-panel__header">
          <h2>Earnings Rate by Strategy</h2>
          <p>Bars show aggregate earnings rate and average expected return from each simulation run.</p>
        </div>
        <div className="price-chart">
          <ResponsiveContainer width="100%" height={340}>
            <BarChart data={data} margin={{ top: 14, right: 16, left: 8, bottom: 12 }}>
              <CartesianGrid strokeDasharray="4 6" stroke="#d6ccc1" />
              <XAxis dataKey="strategyLabel" tickMargin={8} stroke="#6a6159" />
              <YAxis tickFormatter={(value: number) => `${value.toFixed(0)}%`} stroke="#6a6159" width={58} />
              <Tooltip
                formatter={(value: number, name: string) => [
                  `${value.toFixed(2)}%`,
                  name === "earningsRatePct" ? "Earnings Rate" : "Avg Expected Return",
                ]}
              />
              <Legend
                formatter={(value) =>
                  value === "earningsRatePct" ? "Earnings Rate" : "Avg Expected Return"
                }
              />
              <Bar dataKey="earningsRatePct" fill="#d96d2f" radius={[6, 6, 0, 0]} />
              <Bar dataKey="avgExpectedReturnPct" fill="#3f7f93" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      {isLoading && <p className="state-message">Running strategy comparison...</p>}
      {error && <p className="state-message state-message--error">{error}</p>}

      {!isLoading && data.length > 0 && (
        <section className="strategy-table-wrap benefits-table-wrap" aria-label="Strategy comparison metrics">
          <table className="strategy-table">
            <thead>
              <tr>
                <th>Strategy</th>
                <th>Signals</th>
                <th>Buy Yes / Buy No / Hold</th>
                <th>Earnings Rate</th>
                <th>Avg Expected Return</th>
                <th>Executed At (UTC)</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.strategyType}>
                  <td>{row.strategyLabel}</td>
                  <td>{row.signalCount}</td>
                  <td>
                    {row.buyYes} / {row.buyNo} / {row.hold}
                  </td>
                  <td>{row.earningsRatePct.toFixed(2)}%</td>
                  <td>{row.avgExpectedReturnPct.toFixed(2)}%</td>
                  <td className="mono">{new Date(row.executedAt).toISOString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}
