import { useEffect, useMemo, useState } from "react";

import { StrategyResult, fetchStrategies } from "../api/client";

type UseStrategiesState = {
  strategies: StrategyResult[];
  isLoading: boolean;
  error: string | null;
};

export function useStrategies(limit = 100) {
  const [state, setState] = useState<UseStrategiesState>({
    strategies: [],
    isLoading: true,
    error: null,
  });

  useEffect(() => {
    let isMounted = true;

    async function load() {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));

      try {
        const strategies = await fetchStrategies(limit);
        if (isMounted) {
          setState({ strategies, isLoading: false, error: null });
        }
      } catch (error) {
        if (isMounted) {
          setState({
            strategies: [],
            isLoading: false,
            error: error instanceof Error ? error.message : "Unknown error fetching strategies",
          });
        }
      }
    }

    void load();

    return () => {
      isMounted = false;
    };
  }, [limit]);

  const summary = useMemo(() => {
    const total = state.strategies.length;
    const buyYes = state.strategies.filter((row) => row.signal === "buy_yes").length;
    const buyNo = state.strategies.filter((row) => row.signal === "buy_no").length;
    const hold = state.strategies.filter((row) => row.signal === "hold").length;

    const avgExpectedReturnPct =
      total > 0
        ? state.strategies.reduce((sum, row) => sum + row.expected_return_pct, 0) / total
        : 0;

    const weightedConfidence =
      total > 0
        ? state.strategies.reduce((sum, row) => sum + row.confidence, 0) / total
        : 0;

    return {
      total,
      buyYes,
      buyNo,
      hold,
      avgExpectedReturnPct,
      weightedConfidence,
    };
  }, [state.strategies]);

  return {
    ...state,
    summary,
  };
}
