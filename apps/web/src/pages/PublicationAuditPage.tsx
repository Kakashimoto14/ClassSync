import { useEffect, useState } from 'react';
import { timetableRequest } from '../lib/publication-api';
import { schedulingSandboxEnabled } from '../lib/scheduling-api';

type ActivityEvent = {
  event_id: string;
  event_type: string;
  entity_type: string;
  entity_ref: string;
  revision: number | null;
  actor_uid: string;
  created_at: string;
};

const eventLabel: Record<string, string> = {
  'academic.period.created': 'Academic period created',
  'academic.record.created': 'Academic record created',
  'academic.record.updated': 'Academic record updated',
  'academic.calendar.saved': 'Academic calendar saved',
  'scheduling.draft.saved': 'Schedule draft saved',
  'scheduling.publication.published': 'Timetable published',
};

export function PublicationAuditPage() {
  const [periods, setPeriods] = useState<Array<{ id: string; title: string }>>([]);
  const [period, setPeriod] = useState('');
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    timetableRequest<{ periods: Array<{ id: string; title: string }> }>(
      (schedulingSandboxEnabled ? 'sandbox/' : '') + 'periods',
    )
      .then((v) => setPeriods(v.periods))
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!period) return;
    let ignore = false;
    setError('');
    const historyRequest = schedulingSandboxEnabled
      ? timetableRequest<{
          versions: Array<{
            id: string;
            revision: number;
            actor: string;
            created_at: string;
            status: string;
          }>;
        }>(`history/${encodeURIComponent(period)}?dataset=synthetic`).then(({ versions }) =>
          versions.map((version) => ({
            event_id: version.id,
            event_type: 'scheduling.publication.published',
            entity_type: 'publication',
            entity_ref: version.id,
            revision: version.revision,
            actor_uid: version.actor,
            created_at: version.created_at,
          })),
        )
      : timetableRequest<{ events: ActivityEvent[] }>(
          `audit/${encodeURIComponent(period)}`,
        ).then(({ events: rows }) => rows);
    historyRequest
      .then((v) => {
        if (!ignore) setEvents(v);
      })
      .catch((e) => {
        if (!ignore) setError(e.message);
      });
    return () => {
      ignore = true;
    };
  }, [period]);
  return (
    <section className="workspace-card">
      <h2>{schedulingSandboxEnabled ? 'Preview publication history' : 'Administrator activity'}</h2>
      <label>
        Academic period
        <select value={period} onChange={(e) => setPeriod(e.target.value)}>
          <option value="">Choose a period</option>
          {periods.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
      </label>
      {error && <p role="alert">{error}</p>}
      {period && !error && events.length === 0 && (
        <p role="status">No activity is recorded for this period.</p>
      )}
      <ul>
        {events.map((event) => (
          <li key={event.event_id}>
            <strong>{eventLabel[event.event_type] ?? 'Administrative activity'}</strong>
            {' · '}{event.entity_type}
            {event.revision !== null && ` · revision ${event.revision}`}
            {' · '}<time dateTime={event.created_at}>{event.created_at}</time>
            {' · '}Administrator {event.actor_uid}
          </li>
        ))}
      </ul>
      <p className="muted">
        {schedulingSandboxEnabled
          ? 'Preview mode shows publication history only; it is not an authoritative activity audit.'
          : 'Events are recorded by PostgreSQL and contain event metadata only, not academic record payloads.'}
      </p>
    </section>
  );
}
