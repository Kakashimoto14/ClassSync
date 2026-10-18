import { useEffect, useState } from 'react';
import { timetableRequest } from '../lib/publication-api';
import { schedulingSandboxEnabled } from '../lib/scheduling-api';
export function PublicationAuditPage() {
  const [periods, setPeriods] = useState<Array<{ id: string; title: string }>>([]);
  const [period, setPeriod] = useState('');
  const [versions, setVersions] = useState<
    Array<{ id: string; revision: number; actor: string; created_at: string; status: string }>
  >([]);
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
    timetableRequest<{ versions: typeof versions }>(
      `history/${encodeURIComponent(period)}?dataset=${schedulingSandboxEnabled ? 'synthetic' : 'institutional'}`,
    )
      .then((v) => {
        if (!ignore) setVersions(v.versions);
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
      <h2>Publication audit history</h2>
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
      <ul>
        {versions.map((v) => (
          <li key={v.id}>
            {v.status} · version {v.revision} · <time dateTime={v.created_at}>{v.created_at}</time>{' '}
            · {v.actor}
            <p className="draft-id">{v.id}</p>
          </li>
        ))}
      </ul>
      <p className="muted">
        Verified Administrator access is required. This view contains authoritative publication
        versions, not demonstration audit entries.
      </p>
    </section>
  );
}
