import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
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
  type Assignment,
} from '../lib/scheduling-api';
import { requestDraftAdvice, saveDraftRevision } from '../lib/scheduling-api';
import { appMode } from '../config/runtime-config';
const schedulingWorkspaceEnabled = appMode === 'institutional' || schedulingSandboxEnabled;
import { SchedulingTimetable } from './SchedulingTimetable';
import { draftPath } from '../lib/scheduling-labels';
import { PublicationPanel } from './PublicationPanel';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';

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
          <Button onClick={save} loading={busy} disabled={busy || !title.trim()}>
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
  const source =
    appMode !== 'institutional' && search.get('source') === 'synthetic' ? 'synthetic' : 'academic';
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
    if (!schedulingWorkspaceEnabled) return;
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
  if (!schedulingWorkspaceEnabled) return <DraftUnavailable />;
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
        {appMode === 'institutional' ? 'University academic schedules' : 'Development sandbox'} ·{' '}
        {source === 'academic'
          ? 'Saved user-entered academic drafts'
          : 'Saved synthetic test drafts'}{' '}
        · Unpublished
      </p>
      {schedulingSandboxEnabled && (
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
      )}
      <div className="draft-actions">
        <Link className="button" to="/admin/ai-scheduling">
          Generate Weekly Schedule
        </Link>
        <Link className="text-action" to="/admin/schedule-manager">
          Back to Schedule Manager
        </Link>
      </div>
      {!data && !error && <ClassSyncSkeleton layout="table" label="Loading saved drafts" />}
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
  const source =
    appMode === 'institutional' || search.get('source') === 'academic' ? 'academic' : 'synthetic';
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
  const navigate = useNavigate();
  useEffect(() => {
    if (!schedulingWorkspaceEnabled) return;
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
  if (!schedulingWorkspaceEnabled) return <DraftUnavailable />;
  return (
    <div className="weekly-scheduler">
      <Link
        className="text-action"
        to={`/admin/schedule-manager/drafts${source === 'academic' ? '?source=academic' : ''}`}
      >
        Back to Saved Drafts
      </Link>
      {!draft && !error && <ClassSyncSkeleton layout="timetable" label="Loading saved timetable" />}
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
          {source === 'academic' && appMode === 'institutional' && <DraftAdvisorPanel draft={draft} />}
          {source === 'academic' && appMode === 'institutional' && <DraftAssignmentEditor draft={draft} onSaved={(value) => navigate(draftPath(value.id, 'academic'))} />}
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

function DraftAdvisorPanel({ draft }: { draft: DraftDetail }) {
  const [busy, setBusy] = useState(false);
  const [advice, setAdvice] = useState<{
    message: string;
    suggestions: Array<string | { assignment: Assignment; reason: string; also_moves?: Assignment | null }>;
  } | null>(null);
  const [error, setError] = useState('');
  const [targetId, setTargetId] = useState(draft.generation_result.assignments[0]?.id ?? '');
  async function analyze(kind: 'health' | 'conflict') {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const result = await requestDraftAdvice(
        draft.id,
        kind,
        kind === 'conflict'
          ? { assignment_id: targetId }
          : undefined,
      );
      setAdvice(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Advisor is unavailable.');
    } finally {
      setBusy(false);
    }
  }
  async function apply(assignment: Assignment, alsoMoves?: Assignment | null) {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      // A two-step repair moves both sessions together; the server revalidates the whole draft.
      const moves = new Map([assignment, ...(alsoMoves ? [alsoMoves] : [])].map((item) => [item.id, item]));
      const assignments = draft.generation_result.assignments.map((item) => moves.get(item.id) ?? item);
      const value = await saveDraftRevision(draft.id, {
        assignments,
        title: `${draft.title} · revised`,
        idempotency_key: crypto.randomUUID(),
      });
      window.location.assign(draftPath(value.id, 'academic'));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The proposed move failed deterministic validation.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="workspace-card" aria-labelledby="draft-advisor-heading" aria-busy={busy}>
      <h2 id="draft-advisor-heading">Optional schedule advisor</h2>
      <p>Suggestions are advisory. Deterministic validation remains the authority.</p>
      <label>Assignment to review<select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
        {draft.generation_result.assignments.map((item) => <option key={item.id} value={item.id}>
          {draft.input_snapshot.offerings?.find((offering) => offering.id === item.offering_id)?.subject_name ?? item.offering_id}
        </option>)}
      </select></label>
      <div className="draft-actions">
        <Button loading={busy} disabled={busy} onClick={() => void analyze('conflict')}>Ask AI for conflict options</Button>
        <Button variant="secondary" loading={busy} disabled={busy} onClick={() => void analyze('health')}>Analyze Draft with AI</Button>
      </div>
      {error && <p role="alert">{error}</p>}
      {advice && <div role="status"><p>{advice.message}</p><ul>{advice.suggestions.map((item, index) => <li key={typeof item === 'string' ? item : `${item.assignment.id}-${index}`}>
        {typeof item === 'string' ? item : <>{item.reason} · Day {item.assignment.day + 1}, {String(Math.floor(item.assignment.start / 60)).padStart(2, '0')}:{String(item.assignment.start % 60).padStart(2, '0')} · {draft.input_snapshot.rooms?.find((room) => room.id === item.assignment.room_id)?.name}<Button loading={busy} disabled={busy} onClick={() => void apply(item.assignment, item.also_moves)}>Apply as validated revision</Button></>}
      </li>)}</ul></div>}
    </section>
  );
}

function DraftAssignmentEditor({
  draft,
  onSaved,
}: {
  draft: DraftDetail;
  onSaved: (draft: DraftDetail) => void;
}) {
  const assignments: Assignment[] = draft.generation_result.assignments;
  const [selectedId, setSelectedId] = useState(assignments[0]?.id ?? '');
  const [room, setRoom] = useState(assignments[0]?.room_id ?? '');
  const [day, setDay] = useState(assignments[0]?.day ?? 0);
  const [start, setStart] = useState(assignments[0] ? `${String(Math.floor(assignments[0].start / 60)).padStart(2, '0')}:${String(assignments[0].start % 60).padStart(2, '0')}` : '08:00');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const selected = assignments.find((item) => item.id === selectedId);
  function select(id: string) {
    const assignment = assignments.find((item) => item.id === id);
    if (!assignment) return;
    setSelectedId(id);
    setRoom(assignment.room_id);
    setDay(assignment.day);
    setStart(`${String(Math.floor(assignment.start / 60)).padStart(2, '0')}:${String(assignment.start % 60).padStart(2, '0')}`);
  }
  async function save() {
    if (!selected || busy) return;
    const startMinutes = Number(start.slice(0, 2)) * 60 + Number(start.slice(3));
    const changed = assignments.map((item) => item.id === selected.id
      ? { ...item, room_id: room, day, start: startMinutes, end: startMinutes + selected.end - selected.start }
      : item);
    setBusy(true);
    setError('');
    try {
      const value = await saveDraftRevision(draft.id, {
        assignments: changed,
        title: `${draft.title} · revised`,
        idempotency_key: crypto.randomUUID(),
      });
      onSaved(value);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Revision was not saved.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="workspace-card" aria-labelledby="draft-edit-heading" aria-busy={busy}>
      <h2 id="draft-edit-heading">Edit draft assignment</h2>
      <p>Changes create a separate draft. The original remains unchanged until you review and publish the revision.</p>
      <label>Class assignment<select value={selectedId} onChange={(event) => select(event.target.value)}>{assignments.map((item) => <option key={item.id} value={item.id}>{(draft.input_snapshot.offerings ?? []).find((offering) => offering.id === item.offering_id)?.subject_name ?? item.offering_id} · {item.id}</option>)}</select></label>
      {selected && <>
        <label>Room<select value={room} onChange={(event) => setRoom(event.target.value)}>{(draft.input_snapshot.rooms ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label>Day<select value={day} onChange={(event) => setDay(Number(event.target.value))}>{['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'].map((item, index) => <option key={item} value={index}>{item}</option>)}</select></label>
        <label>Start time<input type="time" value={start} onChange={(event) => setStart(event.target.value)} /></label>
      </>}
      {error && <p role="alert">{error}</p>}
      <Button loading={busy} disabled={busy || !selected} onClick={() => void save()}>Save validated revision</Button>
    </section>
  );
}
