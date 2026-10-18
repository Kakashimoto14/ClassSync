import { useEffect, useState } from 'react';
import { Button } from '../components/ui/Button';
import { timetableRequest } from '../lib/publication-api';
import { env } from '../lib/env';
import { OccurrenceExceptionEditor } from './OccurrenceExceptionEditor';
import type { DraftDetail } from '../lib/scheduling-api';

type Version = {
  id: string;
  draft_id: string;
  calendar: Record<string, unknown>;
  revision: number;
  status: string;
  actor: string;
  created_at: string;
  review: { sections: number; teachers: number; rooms: number; occurrences: number };
};
export function PublicationPanel({
  draft,
  source,
}: {
  draft: DraftDetail;
  source: 'synthetic' | 'academic';
}) {
  const [open, setOpen] = useState(false);
  return (
    <details className="workspace-card" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>Review publication</summary>
      {open && <PublicationContent draft={draft} source={source} />}
    </details>
  );
}
function PublicationContent({
  draft,
  source,
}: {
  draft: DraftDetail;
  source: 'synthetic' | 'academic';
}) {
  const [calendar, setCalendar] = useState<Record<string, unknown> | null>(null);
  const [academicRevision, setAcademicRevision] = useState(0);
  const [revision, setRevision] = useState(0);
  const [versions, setVersions] = useState<Version[]>([]);
  const [state, setState] = useState('draft');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<Version['review'] | null>(null);
  const [key, setKey] = useState(() => crypto.randomUUID());
  const dataset = draft.input_snapshot.synthetic ? 'synthetic' : 'institutional';
  useEffect(() => {
    let ignore = false;
    if (source !== 'academic') return;
    Promise.all([
      fetch(`${env.apiBaseUrl}/academic/sandbox/periods/${draft.period_id}`).then((r) => r.json()),
      timetableRequest<{ versions: Version[] }>(`history/${draft.period_id}?dataset=${dataset}`),
    ])
      .then(([p, h]) => {
        if (ignore) return;
        const period = p.data?.period;
        if (!period?.calendar) throw new Error('Academic calendar dates are required.');
        setCalendar(
          h.versions[0]?.draft_id === draft.id ? h.versions[0].calendar : period.calendar,
        );
        if (h.versions[0]?.draft_id === draft.id) setState('published');
        setAcademicRevision(period.revision);
        setVersions(h.versions);
        setRevision(h.versions[0]?.revision ?? 0);
      })
      .catch((e) => {
        if (!ignore) setError(e.message);
      });
    return () => {
      ignore = true;
    };
  }, [draft.id, draft.period_id, source, dataset]);
  async function act(publish: boolean) {
    if (!calendar || busy) return;
    setBusy(true);
    setError('');
    if (publish) setState('publishing');
    try {
      const body = {
        draft_id: draft.id,
        source: dataset === 'synthetic' ? 'academic-sandbox' : 'administrator',
        dataset,
        expected_version: revision,
        expected_academic_revision: academicRevision,
        idempotency_key: key,
        calendar: { ...calendar, published_version: null },
      };
      if (publish) {
        const v = await timetableRequest<Version>('publish', body);
        setState('published');
        setVersions((old) => [v, ...old]);
        setRevision(v.revision);
      } else {
        const r = await timetableRequest<
          Version | (Version['review'] & { current_revision: number })
        >('review', body);
        if ('id' in r) {
          setState('published');
          setVersions((old) => [r, ...old.filter((v) => v.id !== r.id)]);
          setRevision(r.revision);
        } else {
          setReport(r);
          setState('ready-for-review');
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Publication not confirmed');
      const status = (e as { status?: number }).status;
      setState(
        status === 409 || status === 422
          ? 'validation-failed'
          : publish
            ? 'publication-unconfirmed'
            : 'review-unavailable',
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="workspace-card publication-panel" aria-busy={busy}>
      <h2>Schedule publication</h2>
      <p role="status">{state.replaceAll('-', ' ')}</p>
      <p>
        Publication requires a verified Administrator token. Selecting Administrator in the preview
        never grants this permission. Synthetic publication is restricted to the explicitly enabled
        local service.
      </p>
      {calendar && (
        <div className="academic-field-grid">
          <label>
            Effective start
            <input
              type="date"
              value={String(calendar.effective_start)}
              disabled={busy || state === 'published'}
              onChange={(e) => {
                setCalendar({ ...calendar, effective_start: e.target.value });
                setState('draft');
                setReport(null);
              }}
            />
          </label>
          <label>
            Effective end
            <input
              type="date"
              value={String(calendar.effective_end)}
              disabled={busy || state === 'published'}
              onChange={(e) => {
                setCalendar({ ...calendar, effective_end: e.target.value });
                setState('draft');
                setReport(null);
              }}
            />
          </label>
        </div>
      )}
      {source !== 'academic' && (
        <p>Publication requires a draft generated from an effective-dated academic period.</p>
      )}
      {calendar && (
        <OccurrenceExceptionEditor
          draft={draft}
          start={String(calendar.effective_start)}
          exceptions={
            (calendar.exceptions ?? []) as Parameters<
              typeof OccurrenceExceptionEditor
            >[0]['exceptions']
          }
          disabled={busy || state === 'published'}
          onChange={(exceptions) => {
            setCalendar({ ...calendar, exceptions });
            setState('draft');
            setReport(null);
          }}
        />
      )}
      {state === 'published' && (
        <Button
          variant="secondary"
          onClick={() => {
            setState('draft');
            setKey(crypto.randomUUID());
            setReport(null);
          }}
        >
          Prepare revised version
        </Button>
      )}
      {error && <p role="alert">{error}</p>}
      {report && (
        <p>
          Review impact: {report.sections} sections · {report.teachers} teachers · {report.rooms}{' '}
          rooms · {report.occurrences} dated sessions.
        </p>
      )}
      <div className="draft-actions">
        <Button
          variant="secondary"
          disabled={!calendar || busy || state === 'published'}
          onClick={() => void act(false)}
        >
          Revalidate for publication
        </Button>
        <Button disabled={state !== 'ready-for-review' || busy} onClick={() => void act(true)}>
          {busy ? 'Publishing…' : 'Publish reviewed timetable'}
        </Button>
      </div>
      {versions.length > 0 && (
        <details open={state === 'published'}>
          <summary>Publication history and audit</summary>
          <ul>
            {versions.map((v) => (
              <li key={v.id}>
                {v.status} · version {v.revision} · {v.created_at} · {v.actor}
                <p className="draft-id">{v.id}</p>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
