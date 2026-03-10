export type EventItem = {
  id: string;
  title?: string;
  question?: string;
  description?: string;
  participantCount: number;
  yesProbability: number | null;
  isNearFiftyProbability: boolean;
  conditionId?: string;
  marketId?: string;
  clobTokenId?: string;
  clobTokenIds?: string[] | string;
  markets?: Array<{
    conditionId?: string;
    id?: string;
    clobTokenId?: string;
    clobTokenIds?: string[] | string;
  }>;
};

export type PricePoint = {
  timestamp: number;
  price: number;
};

export type PriceHistoryResponse = {
  conditionId: string;
  interval: string;
  history: PricePoint[];
};

export type StrategySignal = "buy_yes" | "buy_no" | "hold";
export type StrategyType = "mean_reversion" | "llm";
export type LlmProvider = "local" | "remote" | "claude";

export type StrategyResult = {
  event_id: string;
  signal: StrategySignal;
  confidence: number;
  expected_return_pct: number;
  earnings_rate_pct?: number;
  rationale: string;
  provider?: string;
  model?: string;
};

export type StrategySimulationRequest = {
  strategy_type: StrategyType;
  limit: number;
  interval_seconds: number;
  provider?: LlmProvider;
  model?: string;
  api_key?: string;
  llm_max_events?: number;
  use_cache?: boolean;
};

export type StrategySimulationResponse = {
  strategy_type: StrategyType;
  provider: LlmProvider | null;
  model: string | null;
  interval_seconds: number;
  executed_at: string;
  next_run_at: string;
  earnings_rate_pct: number;
  results: StrategyResult[];
};

const DEFAULT_API_BASE = "http://localhost:8000";
const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? DEFAULT_API_BASE;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);

  if (!response.ok) {
    let detail = "";
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload?.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      // Ignore JSON parse errors and fall back to generic message.
    }

    throw new Error(
      detail ? `Request failed (${response.status}): ${detail}` : `Request failed (${response.status}): ${path}`
    );
  }

  return (await response.json()) as T;
}

export async function fetchEvents(limit = 100): Promise<EventItem[]> {
  return request<EventItem[]>(`/events?limit=${limit}`);
}

export async function fetchEventById(eventId: string): Promise<EventItem> {
  return request<EventItem>(`/events/${eventId}`);
}

export async function fetchPriceHistory(
  conditionId: string,
  interval = "1d"
): Promise<PriceHistoryResponse> {
  return request<PriceHistoryResponse>(`/prices/${conditionId}?interval=${interval}`);
}

export async function fetchStrategies(limit = 100): Promise<StrategyResult[]> {
  return request<StrategyResult[]>(`/strategies?limit=${limit}`);
}

export async function simulateStrategies(
  payload: StrategySimulationRequest
): Promise<StrategySimulationResponse> {
  return request<StrategySimulationResponse>("/strategies/simulate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}
