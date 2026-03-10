import { Link } from "react-router-dom";

import { EventItem } from "../api/client";

type EventCardProps = {
  event: EventItem;
  rank: number;
};

function formatProbability(probability: number | null) {
  if (probability === null) {
    return "N/A";
  }
  return `${(probability * 100).toFixed(1)}%`;
}

export function EventCard({ event, rank }: EventCardProps) {
  const title = event.title ?? event.question ?? `Event ${event.id}`;

  return (
    <article className="event-card">
      <header className="event-card__header">
        <span className="event-card__rank">#{rank}</span>
        {event.isNearFiftyProbability && <span className="event-card__badge">Near 50%</span>}
      </header>

      <h2 className="event-card__title">{title}</h2>
      {event.description && <p className="event-card__description">{event.description}</p>}

      <dl className="event-card__meta">
        <div>
          <dt>Participants</dt>
          <dd>{event.participantCount.toLocaleString()}</dd>
        </div>
        <div>
          <dt>Yes Probability</dt>
          <dd>{formatProbability(event.yesProbability)}</dd>
        </div>
        <div>
          <dt>Event ID</dt>
          <dd className="event-card__id">{event.id}</dd>
        </div>
      </dl>

      <Link className="event-card__link" to={`/event/${event.id}`}>
        View Detail
      </Link>
    </article>
  );
}
