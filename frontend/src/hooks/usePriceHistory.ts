import { useEffect, useMemo, useState } from "react";

import { PricePoint, fetchPriceHistory } from "../api/client";

type UsePriceHistoryState = {
  history: PricePoint[];
  isLoading: boolean;
  error: string | null;
};

export function usePriceHistory(marketId: string | null, interval = "1d") {
  const [state, setState] = useState<UsePriceHistoryState>({
    history: [],
    isLoading: Boolean(marketId),
    error: null,
  });

  useEffect(() => {
    let isMounted = true;

    async function load() {
      if (!marketId) {
        setState({ history: [], isLoading: false, error: "No market id found for this event." });
        return;
      }

      setState((prev) => ({ ...prev, isLoading: true, error: null }));

      try {
        const response = await fetchPriceHistory(marketId, interval);
        if (isMounted) {
          setState({ history: response.history, isLoading: false, error: null });
        }
      } catch (error) {
        if (isMounted) {
          setState({
            history: [],
            isLoading: false,
            error:
              error instanceof Error
                ? error.message
                : "Unknown error fetching price history",
          });
        }
      }
    }

    void load();

    return () => {
      isMounted = false;
    };
  }, [marketId, interval]);

  const lastPrice = useMemo(() => {
    if (state.history.length === 0) {
      return null;
    }
    return state.history[state.history.length - 1].price;
  }, [state.history]);

  return {
    ...state,
    lastPrice,
  };
}
