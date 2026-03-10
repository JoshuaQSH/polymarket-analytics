import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { EventItem, fetchEventById } from "../api/client";
import { PriceChart } from "../components/PriceChart";
import { usePriceHistory } from "../hooks/usePriceHistory";

function parseTokenIds(tokenIds: string[] | string | undefined): string[] {
  if (!tokenIds) {
    return [];
  }

  if (Array.isArray(tokenIds)) {
    return tokenIds.filter((id): id is string => typeof id === "string" && id.length > 0);
  }

  if (typeof tokenIds !== "string") {
    return [];
  }

  try {
    const parsed = JSON.parse(tokenIds) as unknown;
    if (Array.isArray(parsed)) {
      return parsed.filter((id): id is string => typeof id === "string" && id.length > 0);
    }
  } catch {
    // Fall through to direct token-id handling.
  }

  return tokenIds.length > 0 ? [tokenIds] : [];
}

function extractMarketId(event: EventItem | null): string | null {
  if (!event) {
    return null;
  }

  const directTokens = parseTokenIds(event.clobTokenIds);
  if (directTokens.length > 0) {
    return directTokens[0];
  }

  if (event.clobTokenId) {
    return event.clobTokenId;
  }

  if (event.markets && event.markets.length > 0) {
    for (const market of event.markets) {
      const marketTokens = parseTokenIds(market.clobTokenIds);
      if (marketTokens.length > 0) {
        return marketTokens[0];
      }

      if (market.clobTokenId) {
        return market.clobTokenId;
      }

      if (market.conditionId) {
        return market.conditionId;
      }
    }
  }

  if (event.conditionId) {
    return event.conditionId;
  }

  return null;
}

function formatPercent(value: number | null) {
  if (value === null) {
    return "N/A";
  }
  return `${(value * 100).toFixed(1)}%`;
}

export function EventDetailPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const [event, setEvent] = useState<EventItem | null>(null);
  const [eventLoading, setEventLoading] = useState(true);
  const [eventError, setEventError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadEvent() {
      if (!eventId) {
        setEventLoading(false);
        setEventError("Missing event id.");
        return;
      }

      setEventLoading(true);
      setEventError(null);

      try {
        const loaded = await fetchEventById(eventId);
        if (isMounted) {
          setEvent(loaded);
          setEventLoading(false);
        }
      } catch (error) {
        if (isMounted) {
          setEventLoading(false);
          setEventError(error instanceof Error ? error.message : "Unknown error loading event");
        }
      }
    }

    void loadEvent();

    return () => {
      isMounted = false;
    };
  }, [eventId]);

  const marketId = useMemo(() => extractMarketId(event), [event]);
  const { history, isLoading: historyLoading, error: historyError, lastPrice } = usePriceHistory(
    marketId,
    "1d"
  );

  const title = event?.title ?? event?.question ?? `Event ${eventId}`;

  return (
    <main className="page page--detail">
      <section className="detail-header">
        <div className="hero__actions">
          <Link className="detail-header__back" to="/">
            Back to Event Radar
          </Link>
          <Link className="detail-header__back" to="/strategies">
            Open Strategy Engine
          </Link>
        </div>
        <p className="hero__eyebrow">Event Detail</p>
        <h1 className="hero__title">{title}</h1>
        {event?.description && <p className="hero__subtitle">{event.description}</p>}

        <div className="detail-meta">
          <div>
            <span>Participants</span>
            <strong>{event?.participantCount?.toLocaleString() ?? "-"}</strong>
          </div>
          <div>
            <span>Yes Probability</span>
            <strong>{formatPercent(event?.yesProbability ?? null)}</strong>
          </div>
          <div>
            <span>Last Yes Price</span>
            <strong>{formatPercent(lastPrice)}</strong>
          </div>
          <div>
            <span>Market ID</span>
            <strong className="mono">{marketId ?? "Unavailable"}</strong>
          </div>
        </div>
      </section>

      {eventLoading && <p className="state-message">Loading event...</p>}
      {eventError && <p className="state-message state-message--error">{eventError}</p>}

      {!eventLoading && !eventError && (
        <section className="chart-panel" aria-label="Price history chart">
          <header className="chart-panel__header">
            <h2>Yes / No Price History</h2>
            <p>Derived from CLOB market history (interval: 1d)</p>
          </header>

          {historyLoading && <p className="state-message">Loading history...</p>}
          {historyError && <p className="state-message state-message--error">{historyError}</p>}

          {!historyLoading && !historyError && history.length > 0 && <PriceChart history={history} />}

          {!historyLoading && !historyError && history.length === 0 && (
            <p className="state-message">No price history points returned for this market.</p>
          )}
        </section>
      )}
    </main>
  );
}
