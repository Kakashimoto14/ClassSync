import { useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import {
  listSchedulingDrafts,
  loadSchedulingDraft,
  saveSchedulingDraft,
  schedulingSandboxEnabled,
  type DraftDetail,
  type DraftList,
  type GenerationResult,
} from '../lib/scheduling-api';
import { SchedulingTimetable } from './SchedulingTimetable';
import { draftPath } from '../lib/scheduling-labels';
import { PublicationPanel } from './PublicationPanel';

const created = (value: string) =>
  new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });

export function SaveDraftPanel({
  result,
  source = 'synthetic',
  defaultTitle,
}: {
  result: GenerationResult;
  source?: 'synthetic' | 'academic';
  defaultTitle?: string;
}) {
  const [title, setTitle] = useState(defaultTitle ?? `${result.period_id} — review draft`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState<DraftDetail | null>(null);
  const [key] = useState(() => crypto.randomUUID());
  const active = useRef(false);
  const savedHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (saved) savedHeading.current?.focus();
  }, [saved]);
  async function save() {
    if (active.current || saved || !title.trim()) return;
    active.current = true;
    setBusy(true);
    setError('');
    try {
      const body = {
        run_id: result.run_id,
        input_hash: result.input_hash,
        title: title.trim(),
        idempotency_key: key,
      };
      setSaved(
        await (source === 'academic'
          ? saveSchedulingDraft(body, source)
          : saveSchedulingDraft(body)),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Draft save failed. Retry safely.');
    } finally {
      active.current = false;
      setBusy(false);
    }
  }
  return (
    <section
      className="workspace-card draft-save"
      aria-labelledby="save-draft-heading"
      aria-busy={busy}
    >
      <h3 id="save-draft-heading" ref={savedHeading} tabIndex={-1}>
        {saved ? 'Draft saved' : 'Keep this validated timetable'}
      </h3>
      {saved ? (
        <>
          <p role="status">Saved as “{saved.title}”. Draft · Unpublished.</p>
          <p className="draft-id">Draft ID: {saved.id}</p>
          <Link className="button" to={draftPath(saved.id, source)}>
            Open saved draft
          </Link>
          <Link
            className="text-action"
            to={`/admin/schedule-manager/drafts${source === 'academic' ? '?source=academic' : ''}`}
          >
            View Saved Drafts
          </Link>
        </>
      ) : (
        <>
          <label>
            Draft title
            <input
              value={title}
              maxLength={160}
              disabled={busy}
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          <Button onClick={save} disabled={busy || !title.trim()}>
            {busy ? 'Saving draft…' : 'Save Draft'}
          </Button>
          <p role="status">
            {busy
              ? 'Saving the validated server-held timetable. Please wait.'
              : 'Saving creates an unpublished draft. Student and Teacher schedules stay unchanged.'}
          </p>
          {error && (
            <p role="alert">
              {error} Retry with the same title, or check Saved Drafts if the connection was
              interrupted.
            </p>
          )}
        </>
      )}
    </section>
  );
}

function DraftUnavailable() {
  return (
    <p>
      The saved synthetic-draft workflow is available only in the development scheduling sandbox.
    </p>
  );
}

export function SavedDraftsPage() {
  const [search, setSearch] = useSearchParams();
  const source = search.get('source') === 'synthetic' ? 'synthetic' : 'academic';
  return (
    <DraftListContent
      key={source}
      source={source}
      onSource={(value) => {
        const next = new URLSearchParams(search);
        next.set('source', value);
        setSearch(next);
      }}
    />
  );
}

function DraftListContent({
  source,
  onSource,
}: {
  source: 'synthetic' | 'academic';
  onSource: (value: string) => void;
}) {
  const [data, setData] = useState<DraftList | null>(null);
  const [error, setError] = useState('');
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!schedulingSandboxEnabled) return;
    let ignore = false;
    (source === 'academic' ? listSchedulingDrafts(offset, source) : listSchedulingDrafts(offset))
      .then((value) => {
        if (!ignore) setData(value);
      })
      .catch((e) => {
        if (!ignore) setError(e instanceof Error ? e.message : 'Draft list unavailable.');
      });
    return () => {
      ignore = true;
    };
  }, [offset, retry, source]);
  if (!schedulingSandboxEnabled) return <DraftUnavailable />;
  const reload = () => {
    setData(null);
    setError('');
    setRetry((n) => n + 1);
  };
  const move = (next: number) => {
    setData(null);
    setError('');
    setOffset(next);
  };
  return (
    <div className="weekly-scheduler">
      <p className="scheduling-boundary">
        Development sandbox ·{' '}
        {source === 'academic'
          ? 'Saved user-entered academic drafts'
          : 'Saved synthetic test drafts'}{' '}
        · Unpublished
      </p>
      <details>
        <summary>Browse another draft collection</summary>
        <label>
          Draft source
          <select value={source} onChange={(e) => onSource(e.target.value)}>
            <option value="academic">Academic schedules</option>
            <option value="synthetic">Engine test samples</option>
          </select>
        </label>
      </details>
      <div className="draft-actions">
        <Link className="button" to="/admin/ai-scheduling">
          Generate Weekly Schedule
        </Link>
        <Link className="text-action" to="/admin/schedule-manager">
          Back to Schedule Manager
        </Link>
      </div>
      {!data && !error && <p role="status">Loading saved drafts…</p>}
      {error && (
        <div className="scheduler-error" role="alert">
          <p>{error}</p>
          <Button variant="secondary" onClick={reload}>
            Retry loading drafts
          </Button>
        </div>
      )}
      {data && (
        <>
          <p role="status">
            {data.drafts.length
              ? `Showing ${offset + 1}–${offset + data.drafts.length} saved drafts.`
              : 'No saved drafts yet. Generate and validate a timetable, then save it here.'}
          </p>
          <ul className="saved-drafts-list" aria-label="Saved scheduling drafts">
            {data.drafts.map((draft) => (
              <li key={draft.id} className="workspace-card saved-draft-row">
                <div>
                  <h2>{draft.title}</h2>
                  <p>
                    <time dateTime={draft.created_at}>{created(draft.created_at)}</time>
                  </p>
                  <p>
                    {draft.offerings_scheduled}/{draft.offerings_requested} offerings ·{' '}
                    {draft.session_count} sessions · {draft.allocated_minutes}/
                    {draft.required_minutes} min
                  </p>
                </div>
                <div className="draft-actions">
                  <StatusBadge tone="neutral">Draft · Unpublished</StatusBadge>
                  <StatusBadge tone={draft.validated ? 'success' : 'warning'}>
                    {draft.validated
                      ? `Validated · ${draft.hard_conflict_count} conflicts`
                      : 'Validation unavailable'}
                  </StatusBadge>
                  <span className="source-label">
                    {draft.source === 'development-entered'
                      ? 'Local academic records'
                      : draft.source === 'synthetic-preview'
                        ? 'Synthetic engine sample'
                        : 'Institutional'}{' '}
                    · {draft.solver_status}
                  </span>
                  <Link
                    className="button button--secondary"
                    to={draftPath(draft.id, source)}
                    aria-label={`Open Draft: ${draft.title}`}
                  >
                    Open Draft
                  </Link>
                </div>
              </li>
            ))}
          </ul>
          <nav className="draft-actions" aria-label="Saved drafts pagination">
            <Button
              variant="secondary"
              disabled={offset === 0}
              onClick={() => move(Math.max(0, offset - 25))}
            >
              Previous
            </Button>
            <Button variant="secondary" disabled={!data.has_more} onClick={() => move(offset + 25)}>
              Next
            </Button>
          </nav>
        </>
      )}
    </div>
  );
}

export function SavedDraftDetailPage() {
  const { draftId = '' } = useParams();
  const [search] = useSearchParams();
  const source = search.get('source') === 'academic' ? 'academic' : 'synthetic';
  return <DraftDetailContent key={`${source}:${draftId}`} draftId={draftId} source={source} />;
}

function DraftDetailContent({
  draftId,
  source,
}: {
  draftId: string;
  source: 'synthetic' | 'academic';
}) {
  const [draft, setDraft] = useState<DraftDetail | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (!schedulingSandboxEnabled) return;
    let ignore = false;
    (source === 'academic' ? loadSchedulingDraft(draftId, source) : loadSchedulingDraft(draftId))
      .then((value) => {
        if (!ignore) setDraft(value);
      })
      .catch((e) => {
        if (!ignore) setError(e instanceof Error ? e.message : 'Draft unavailable.');
      });
    return () => {
      ignore = true;
    };
  }, [draftId, retry, source]);
  useEffect(() => {
    if (draft) heading.current?.focus({ preventScroll: true });
  }, [draft]);
  if (!schedulingSandboxEnabled) return <DraftUnavailable />;
  return (
    <div className="weekly-scheduler">
      <Link
        className="text-action"
        to={`/admin/schedule-manager/drafts${source === 'academic' ? '?source=academic' : ''}`}
      >
        Back to Saved Drafts
      </Link>
      {!draft && !error && <p role="status">Loading saved timetable…</p>}
      {error && (
        <div className="scheduler-error" role="alert">
          <p>{error}</p>
          <Button
            variant="secondary"
            onClick={() => {
              setError('');
              setRetry((n) => n + 1);
            }}
          >
            Retry loading draft
          </Button>
        </div>
      )}
      {draft && (
        <>
          <section
            className="workspace-card saved-draft-summary"
            aria-labelledby="saved-draft-title"
          >
            <h2 id="saved-draft-title" tabIndex={-1} ref={heading}>
              {draft.title}
            </h2>
            <div className="draft-actions">
              <StatusBadge tone="neutral">Draft · Unpublished</StatusBadge>
              <StatusBadge tone="success">{`Validated · ${draft.solver_status}`}</StatusBadge>
            </div>
            <p className="scheduling-boundary">
              {draft.source === 'synthetic-preview'
                ? 'Synthetic preview'
                : draft.source === 'development-entered'
                  ? 'Development-entered academic data'
                  : 'Institutional data'}{' '}
              · Immutable draft snapshot. Publication creates a separate version; saving or
              reopening this draft never publishes it.
            </p>
            <p role="status">
              {draft.offerings_scheduled}/{draft.offerings_requested} offerings ·{' '}
              {draft.session_count} sessions · {draft.allocated_minutes}/{draft.required_minutes}{' '}
              instructional minutes · {draft.hard_conflict_count} hard conflicts
            </p>
            <p>
              {draft.period_id} · Saved{' '}
              <time dateTime={draft.created_at}>{created(draft.created_at)}</time>
            </p>
            <p className="draft-id">Draft ID: {draft.id}</p>
          </section>
          <SchedulingTimetable
            key={draft.id}
            input={draft.input_snapshot}
            result={draft.generation_result}
          />
          <PublicationPanel draft={draft} source={source} />
          {source === 'academic' && draft.input_snapshot.synthetic && (
            <Link
              className="button button--secondary"
              to={`/admin/calendar?review=${encodeURIComponent(draft.id)}`}
            >
              Review generated calendar
            </Link>
          )}
          <section aria-label="Saved draft validation">
            <h2>Independent validation</h2>
            <p>
              Passed: the complete saved assignments satisfy the input snapshot. No solver
              regeneration was performed.
            </p>
          </section>
          <details>
            <summary>Saved draft provenance</summary>
            <p>
              Creator: {draft.creator} · Data version: {draft.data_version} · Schema:{' '}
              {draft.schema_version}
            </p>
            <p>Run: {draft.run_id}</p>
            <p>Input SHA-256: {draft.input_hash}</p>
            <p>
              {draft.generation_result.metadata.solver}{' '}
              {draft.generation_result.metadata.solver_version} · seed{' '}
              {draft.generation_result.metadata.seed} · objective{' '}
              {draft.generation_result.metadata.objective ?? 'unavailable'} · bound{' '}
              {draft.generation_result.metadata.best_bound ?? 'unavailable'}
            </p>
          </details>
        </>
      )}
    </div>
  );
}
