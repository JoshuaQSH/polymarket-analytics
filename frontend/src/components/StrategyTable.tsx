import { StrategyResult } from "../api/client";

type StrategyTableProps = {
  strategies: StrategyResult[];
  bankrollUsd: number;
  allocationPct: number;
};

function formatSignal(signal: StrategyResult["signal"]) {
  if (signal === "buy_yes") {
    return "Buy Yes";
  }
  if (signal === "buy_no") {
    return "Buy No";
  }
  return "Hold";
}

function estimateTradeUsd(bankrollUsd: number, allocationPct: number) {
  return bankrollUsd * (allocationPct / 100);
}

function estimateStrategyPnlUsd(
  strategy: StrategyResult,
  bankrollUsd: number,
  allocationPct: number
) {
  const tradeNotional = estimateTradeUsd(bankrollUsd, allocationPct);
  return tradeNotional * strategy.confidence * (strategy.expected_return_pct / 100);
}

function estimateEarningsRatePct(strategy: StrategyResult) {
  return strategy.earnings_rate_pct ?? strategy.confidence * strategy.expected_return_pct;
}

export function StrategyTable({
  strategies,
  bankrollUsd,
  allocationPct,
}: StrategyTableProps) {
  return (
    <div className="strategy-table-wrap">
      <table className="strategy-table">
        <thead>
          <tr>
            <th>Event</th>
            <th>Signal</th>
            <th>Confidence</th>
            <th>Expected Return</th>
            <th>Earnings Rate</th>
            <th>Est. PnL / Trade</th>
            <th>Rationale</th>
          </tr>
        </thead>
        <tbody>
          {strategies.map((strategy) => {
            const estPnlUsd = estimateStrategyPnlUsd(strategy, bankrollUsd, allocationPct);
            const earningsRate = estimateEarningsRatePct(strategy);
            const signalClass = `signal signal--${strategy.signal}`;

            return (
              <tr key={strategy.event_id}>
                <td>
                  <code>{strategy.event_id}</code>
                  {strategy.provider && strategy.model && (
                    <div className="strategy-table__engine">
                      {strategy.provider}:{strategy.model}
                    </div>
                  )}
                </td>
                <td>
                  <span className={signalClass}>{formatSignal(strategy.signal)}</span>
                </td>
                <td>{(strategy.confidence * 100).toFixed(1)}%</td>
                <td>{strategy.expected_return_pct.toFixed(2)}%</td>
                <td>{earningsRate.toFixed(2)}%</td>
                <td>${estPnlUsd.toFixed(2)}</td>
                <td className="strategy-table__rationale">{strategy.rationale}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
