import { useEffect, useState } from 'react';
import { timetableRequest } from '../lib/publication-api';
import { schedulingSandboxEnabled } from '../lib/scheduling-api';

const HISTORY_PAGE_SIZE = 50;

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
  const [historyOffset, setHistoryOffset] = useState(0);
  const [historyHasMore, setHistoryHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
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
    setHistoryHasMore(false);
    setLoading(true);
    const historyRequest = schedulingSandboxEnabled
      ? timetableRequest<{
          has_more?: boolean;
          versions: Array<{
            id: string;
            revision: number;
            actor: string;
            created_at: string;
            status: string;
          }>;
        }>(
          'history/' +
            encodeURIComponent(period) +
            '?dataset=synthetic&limit=' +
            HISTORY_PAGE_SIZE +
            '&offset=' +
            historyOffset,
        ).then(({ versions, has_more }) => {
          if (!ignore) setHistoryHasMore(Boolean(has_more));
          return versions.map((version) => ({
            event_id: version.id,
            event_type: 'scheduling.publication.published',
            entity_type: 'publication',
            entity_ref: version.id,
            revision: version.revision,
            actor_uid: version.actor,
            created_at: version.created_at,
          }));
        })
      : timetableRequest<{ events: ActivityEvent[] }>(
          `audit/${encodeURIComponent(period)}`,
        ).then(({ events: rows }) => rows);
    historyRequest
      .then((v) => {
        if (!ignore) {
          setEvents(v);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!ignore) {
          setError(e.message);
          setLoading(false);
        }
      });
    return () => {
      ignore = true;
    };
  }, [period, historyOffset]);
  return (
    <section className="workspace-card">
      <h2>{schedulingSandboxEnabled ? 'Preview publication history' : 'Administrator activity'}</h2>
      <label>
        Academic period
        <select
          value={period}
          onChange={(e) => {
            setHistoryOffset(0);
            setPeriod(e.target.value);
          }}
        >
          <option value="">Choose a period</option>
          {periods.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
      </label>
      {error && <p role="alert">{error}</p>}
      {loading && <p role="status">Loading activity…</p>}
      {period && !error && !loading && events.length === 0 && (
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
      {schedulingSandboxEnabled && period && !error && (
        <nav aria-label="Publication history pages">
          <button
            type="button"
            disabled={loading || historyOffset === 0}
            onClick={() => setHistoryOffset((current) => Math.max(0, current - HISTORY_PAGE_SIZE))}
          >
            Newer history
          </button>
          <span>Page {Math.floor(historyOffset / HISTORY_PAGE_SIZE) + 1}</span>
          <button
            type="button"
            disabled={loading || !historyHasMore}
            onClick={() => setHistoryOffset((current) => current + HISTORY_PAGE_SIZE)}
          >
            Older history
          </button>
        </nav>
      )}
      <p className="muted">
        {schedulingSandboxEnabled
          ? 'Preview mode shows publication history only; it is not an authoritative activity audit.'
          : 'Events are recorded by PostgreSQL and contain event metadata only, not academic record payloads.'}
      </p>
    </section>
  );
}
