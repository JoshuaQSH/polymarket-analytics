import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  LlmProvider,
  StrategyResult,
  StrategySimulationResponse,
  StrategyType,
  simulateStrategies,
} from "../api/client";

type StrategySimulationConfig = {
  strategyType: StrategyType;
  limit: number;
  intervalSeconds: number;
  provider: LlmProvider;
  model: string;
  apiKey: string;
  llmMaxEvents: number;
  useCache: boolean;
};

type UseStrategySimulationState = {
  strategies: StrategyResult[];
  simulation: StrategySimulationResponse | null;
  isLoading: boolean;
  error: string | null;
};

const DEFAULT_CONFIG: StrategySimulationConfig = {
  strategyType: "mean_reversion",
  limit: 100,
  intervalSeconds: 60,
  provider: "local",
  model: "tinyllama",
  apiKey: "",
  llmMaxEvents: 5,
  useCache: true,
};

export function useStrategySimulation(initialConfig: StrategySimulationConfig = DEFAULT_CONFIG) {
  const [config, setConfig] = useState<StrategySimulationConfig>(initialConfig);
  const [autoRunEnabled, setAutoRunEnabled] = useState(false);
  const [nowMs, setNowMs] = useState(Date.now());
  const [state, setState] = useState<UseStrategySimulationState>({
    strategies: [],
    simulation: null,
    isLoading: false,
    error: null,
  });

  const inFlightRef = useRef(false);

  const runOnce = useCallback(async () => {
    if (inFlightRef.current) {
      return;
    }

    inFlightRef.current = true;
    setState((prev) => ({ ...prev, isLoading: true, error: null }));

    try {
      const payload = {
        strategy_type: config.strategyType,
        limit: config.limit,
        interval_seconds: config.intervalSeconds,
        provider: config.provider,
        model: config.model,
        api_key: config.apiKey || undefined,
        llm_max_events: config.llmMaxEvents,
        use_cache: config.useCache,
      } as const;

      const response = await simulateStrategies(payload);
      setState({
        strategies: response.results,
        simulation: response,
        isLoading: false,
        error: null,
      });
    } catch (error) {
      setState((prev) => ({
        ...prev,
        strategies: [],
        isLoading: false,
        error: error instanceof Error ? error.message : "Unknown error running strategy simulation",
      }));
    } finally {
      inFlightRef.current = false;
    }
  }, [config]);

  useEffect(() => {
    if (!autoRunEnabled) {
      return;
    }

    void runOnce();
    const timer = window.setInterval(() => {
      void runOnce();
    }, config.intervalSeconds * 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, [autoRunEnabled, config.intervalSeconds, runOnce]);

  useEffect(() => {
    if (!autoRunEnabled) {
      return;
    }

    const timer = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);

    return () => {
      window.clearInterval(timer);
    };
  }, [autoRunEnabled]);

  const countdownSeconds = useMemo(() => {
    if (!state.simulation?.next_run_at) {
      return null;
    }
    const nextRunMs = new Date(state.simulation.next_run_at).getTime();
    if (!Number.isFinite(nextRunMs)) {
      return null;
    }
    return Math.max(0, Math.ceil((nextRunMs - nowMs) / 1000));
  }, [state.simulation, nowMs]);

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

    const avgEarningsRatePct =
      total > 0
        ? state.strategies.reduce((sum, row) => {
            const earnings =
              row.earnings_rate_pct !== undefined
                ? row.earnings_rate_pct
                : row.confidence * row.expected_return_pct;
            return sum + earnings;
          }, 0) / total
        : 0;

    return {
      total,
      buyYes,
      buyNo,
      hold,
      avgExpectedReturnPct,
      weightedConfidence,
      avgEarningsRatePct,
    };
  }, [state.strategies]);

  return {
    config,
    setConfig,
    autoRunEnabled,
    setAutoRunEnabled,
    runOnce,
    countdownSeconds,
    summary,
    ...state,
  };
}
