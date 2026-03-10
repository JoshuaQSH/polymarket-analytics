import { useEffect, useMemo, useState } from "react";

import { EventItem, fetchEvents } from "../api/client";

type UseEventsState = {
  events: EventItem[];
  isLoading: boolean;
  error: string | null;
};

export function useEvents(limit = 100) {
  const [state, setState] = useState<UseEventsState>({
    events: [],
    isLoading: true,
    error: null,
  });

  useEffect(() => {
    let isMounted = true;

    async function load() {
      setState((prev) => ({ ...prev, isLoading: true, error: null }));
      try {
        const events = await fetchEvents(limit);
        if (isMounted) {
          setState({ events, isLoading: false, error: null });
        }
      } catch (error) {
        if (isMounted) {
          setState({
            events: [],
            isLoading: false,
            error: error instanceof Error ? error.message : "Unknown error fetching events",
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
    const nearFiftyCount = state.events.filter((event) => event.isNearFiftyProbability).length;
    const avgParticipants =
      state.events.length > 0
        ? Math.round(
            state.events.reduce((total, event) => total + event.participantCount, 0) /
              state.events.length
          )
        : 0;

    return {
      totalEvents: state.events.length,
      nearFiftyCount,
      avgParticipants,
    };
  }, [state.events]);

  return {
    ...state,
    summary,
  };
}
