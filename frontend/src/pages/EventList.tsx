import { Link } from "react-router-dom";

import { EventCard } from "../components/EventCard";
import { useEvents } from "../hooks/useEvents";

export function EventListPage() {
  const { events, isLoading, error, summary } = useEvents(100);

  return (
    <main className="page">
      <section className="hero">
        <p className="hero__eyebrow">Polymarket Analytics</p>
        <h1 className="hero__title">Event Radar</h1>
        <p className="hero__subtitle">
          Ranked by participant count with near-50% probability signals highlighted for fast triage.
        </p>

        <div className="hero__actions">
          <Link className="hero__cta" to="/strategies">
            Open Strategy Engine
          </Link>
          <Link className="hero__cta" to="/strategy-benefits">
            View Benefit Plot
          </Link>
        </div>

        <div className="stats-grid">
          <article className="stat-card">
            <p>Total Events</p>
            <strong>{summary.totalEvents}</strong>
          </article>
          <article className="stat-card">
            <p>Near 50%</p>
            <strong>{summary.nearFiftyCount}</strong>
          </article>
          <article className="stat-card">
            <p>Avg Participants</p>
            <strong>{summary.avgParticipants}</strong>
          </article>
        </div>
      </section>

      {isLoading && <p className="state-message">Loading events...</p>}
      {error && <p className="state-message state-message--error">{error}</p>}

      {!isLoading && !error && (
        <section className="event-grid" aria-label="Ranked events">
          {events.map((event, index) => (
            <EventCard key={event.id} event={event} rank={index + 1} />
          ))}
        </section>
      )}
    </main>
  );
}
