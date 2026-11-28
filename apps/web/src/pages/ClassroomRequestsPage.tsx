import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import { institutionalRequest } from '../lib/institutional-api';
import { rolePath } from '../routes/route-config';
import { IssueTriagePanel } from './IssueTriagePanel';
import { useScheduleWorkspace } from '../lib/use-schedule-workspace';
import { periodLabel } from '../lib/workspace-context';
import type { CalendarOccurrence } from '../lib/calendar-model';

export interface ClassroomRequest {
  id: string;
  period_id: string;
  publication_id: string;
  draft_id?: string;
  status: 'pending' | 'approved' | 'rejected' | 'fulfilled';
  revision: number;
  reason: string;
  decision_note: string | null;
  created_at?: string;
  updated_at?: string;
  context: {
    class: CalendarOccurrence;
    proposed_room: { id: string; name: string };
    original_date: string;
  };
}
type Role = 'teacher' | 'administrator';
const stateLabel = {
  pending: 'Awaiting review',
  approved: 'Approved · awaiting publication',
  rejected: 'Not approved',
  fulfilled: 'Classroom change published',
};
type Preflight = {
  state: 'clear' | 'conflict' | 'stale' | 'decided';
  reasons: string[];
};
type RoomOption = {
  id: string;
  name: string;
  capacity?: number | null;
  occupancy?: 'available' | 'occupied';
};
// Each check reviews the whole semester, so only the first few pending cards auto-check.
const AUTO_PREFLIGHT_LIMIT = 5;
const NOT_FOUND = 'Request not found. It does not exist or it is not yours.';
const moment = (value?: string) => {
  const parsed = value ? new Date(value.replace(' ', 'T')) : null;
  return parsed && !Number.isNaN(parsed.getTime())
    ? new Intl.DateTimeFormat('en-PH', {
        dateStyle: 'medium',
        timeStyle: 'short',
        timeZone: 'Asia/Manila',
      }).format(parsed)
    : 'Time not recorded';
};

/** Only what the stored request records: submission, latest state and when it last changed. */
function StatusHistory({ request }: { request: ClassroomRequest }) {
  return (
    <section aria-label="Status history">
      <h3>Status history</h3>
      <ol>
        <li>Submitted · {moment(request.created_at)}</li>
        {request.status === 'fulfilled' && <li>Approved by an Administrator</li>}
        <li>
          {stateLabel[request.status]}
          {request.status !== 'pending' && ` · ${moment(request.updated_at)}`}
        </li>
      </ol>
    </section>
  );
}

function RequestPreflight({
  requestId,
  auto,
  refresh,
  onResult,
}: {
  requestId: string;
  auto: boolean;
  refresh: number;
  onResult: (result: Preflight | null) => void;
}) {
  const [result, setResult] = useState<Preflight | null>(null);
  const [checking, setChecking] = useState(false);
  const [failed, setFailed] = useState('');
  const [requested, setRequested] = useState(auto ? 1 : 0);
  useEffect(() => {
    if (!requested) return;
    const controller = new AbortController();
    setChecking(true);
    setFailed('');
    institutionalRequest<Preflight>(`timetables/requests/${encodeURIComponent(requestId)}/preflight`, {
      role: 'administrator',
      signal: controller.signal,
      timeout: 30000,
    })
      .then((value) => {
        if (controller.signal.aborted) return;
        setResult(value);
        onResult(value);
      })
      .catch((failure) => {
        if (controller.signal.aborted) return;
        setResult(null);
        onResult(null);
        setFailed(failure instanceof Error ? failure.message : 'Conflict check unavailable.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setChecking(false);
      });
    return () => controller.abort();
    // onResult is a stable state setter wrapper owned by the parent card.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestId, requested, refresh]);
  const label =
    result?.state === 'clear'
      ? 'No conflicts · ready to publish'
      : result?.state === 'conflict'
        ? 'Conflict found'
        : result?.state === 'stale'
          ? 'Request out of date'
          : null;
  return (
    <div className="admin-request-preflight" aria-live="polite">
      {checking && <p className="muted">Checking live schedule conflicts…</p>}
      {!checking && label && (
        <p>
          <span className={`admin-request-status admin-request-status--${result?.state}`}>
            {label}
          </span>
          {result?.reasons?.length ? ` ${result.reasons.join(' ')}` : ''}
        </p>
      )}
      {!checking && failed && <p role="alert">{failed}</p>}
      {!checking && (
        <Button variant="secondary" onClick={() => setRequested((value) => value + 1)}>
          {result || failed ? 'Re-check conflicts' : 'Check conflicts'}
        </Button>
      )}
    </div>
  );
}

export function ClassroomRequestsPage({
  role,
  create = false,
  detail = false,
}: {
  role: Role;
  create?: boolean;
  detail?: boolean;
}) {
  const [params, setParams] = useSearchParams();
  const detailId = detail ? (params.get('id') ?? '') : '';
  const issuesTab = role === 'administrator' && !detail && params.get('tab') === 'issues';
  const [missing, setMissing] = useState(false);
  const [requests, setRequests] = useState<ClassroomRequest[] | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  const [statusFilter, setStatusFilter] = useState<ClassroomRequest['status'] | 'all'>('all');
  const [preflight, setPreflight] = useState<Record<string, Preflight | null>>({});
  const [recheck, setRecheck] = useState(0);
  useEffect(() => {
    if (create) return;
    const controller = new AbortController();
    setRequests(null);
    setError('');
    setNotice('');
    setMissing(false);
    if (detail && !detailId) {
      setMissing(true);
      return;
    }
    const options = { role, signal: controller.signal };
    const load = detail
      ? institutionalRequest<ClassroomRequest>(
          `timetables/requests/${encodeURIComponent(detailId)}`,
          options,
        ).then((row) => [row])
      : institutionalRequest<{ requests: ClassroomRequest[] }>('timetables/requests', options).then(
          (data) => data.requests,
        );
    load
      .then((rows) => {
        if (!controller.signal.aborted) setRequests(rows);
      })
      .catch((failure) => {
        if (controller.signal.aborted) return;
        // A malformed, unknown or foreign identifier is reported the same way.
        if (detail && [403, 404, 422].includes(failure.status)) setMissing(true);
        else setError(failure.message);
      });
    return () => controller.abort();
  }, [role, reload, create, detail, detailId]);
  const decide = async (
    request: ClassroomRequest,
    decision: 'approved' | 'rejected' | 'fulfilled',
  ) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const updated = await institutionalRequest<ClassroomRequest>(
        `timetables/requests/${request.id}/${decision === 'fulfilled' ? 'fulfill' : 'decision'}`,
        {
          role,
          method: 'POST',
          body: {
            expected_revision: request.revision,
            ...(decision === 'fulfilled' ? {} : { decision, note: notes[request.id] ?? '' }),
          },
        },
      );
      setRequests(
        (current) =>
          current?.map((row) => (row.id === request.id ? { ...row, ...updated } : row)) ?? null,
      );
      setNotice(
        updated.status === 'fulfilled'
          ? 'Classroom change published. The Teacher and affected students see the updated room.'
          : stateLabel[updated.status],
      );
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : 'The decision was not confirmed. Reload and retry.',
      );
      // A conflict may have appeared since the last check; refresh the live status.
      setRecheck((value) => value + 1);
    } finally {
      setBusy(false);
    }
  };
  if (create) return <CreateClassroomRequest />;
  // A detail page only ever shows the requested identifier, never another request.
  const shown = requests?.filter((request) =>
    detail ? request.id === detailId : statusFilter === 'all' || request.status === statusFilter,
  );
  const unavailable = detail && (missing || (requests !== null && !shown?.length));
  const tabs = role === 'administrator' && !detail && (
    <div className="admin-filter-pills" role="group" aria-label="Request type">
      {(['requests', 'issues'] as const).map((tab) => (
        <button
          key={tab}
          type="button"
          aria-pressed={issuesTab === (tab === 'issues')}
          onClick={() => setParams(tab === 'issues' ? { tab } : {})}
        >
          {tab === 'issues' ? 'Issue reports' : 'Classroom requests'}
        </button>
      ))}
    </div>
  );
  if (issuesTab)
    return (
      <section className="admin-requests">
        {tabs}
        <IssueTriagePanel />
      </section>
    );
  return (
    <section className="admin-requests" aria-busy={busy}>
      {tabs}
      <div className="admin-screen-actions admin-requests-actions">
        {detail && (
          <Link className="text-action" to={rolePath(role, 'requests')}>
            Back to requests
          </Link>
        )}
        {role === 'teacher' && !detail && (
          <Link className="button" to="/teacher/change-requests/new">
            Request a classroom change
          </Link>
        )}
        <Button variant="secondary" onClick={() => setReload((value) => value + 1)} disabled={busy}>
          Reload requests
        </Button>
      </div>
      {role === 'administrator' && !detail && (
        <div className="admin-filter-pills" role="group" aria-label="Filter classroom requests">
          {(['all', 'pending', 'approved', 'rejected', 'fulfilled'] as const).map((status) => {
            const count = status === 'all' ? requests?.length ?? 0 : requests?.filter((item) => item.status === status).length ?? 0;
            const label = status === 'all' ? 'All' : stateLabel[status];
            return <button key={status} type="button" aria-pressed={statusFilter === status} onClick={() => setStatusFilter(status)}>{label}<span>{count}</span></button>;
          })}
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!requests && !error && !missing && <ClassSyncSkeleton layout="rows" label="Loading classroom requests" />}
      {unavailable && <p className="workspace-card admin-empty" role="status">{NOT_FOUND}</p>}
      {!detail && requests?.length === 0 && <p className="workspace-card admin-empty">No classroom requests yet.</p>}
      {!detail && requests?.length && !shown?.length ? <p className="workspace-card admin-empty">No requests match this status.</p> : null}
      {!missing && shown?.map((request) => {
        const pendingIndex = (requests ?? []).filter((item) => item.status === 'pending').indexOf(request);
        const blocked = ['conflict', 'stale'].includes(preflight[request.id]?.state ?? '');
        return (
        <article className="workspace-card admin-request-card" key={request.id}>
          <header className="admin-request-card__header"><div><span className={`admin-request-status admin-request-status--${request.status}`}>{stateLabel[request.status]}</span><h2>
            {request.context.class.subject.code} · {request.context.class.subject.name}
          </h2></div><span className="admin-request-card__date">{request.context.class.date}</span></header>
          <div className="admin-request-metadata"><span>
            {request.context.class.date} · {request.context.class.section.name}
          </span><span>
            {request.context.class.room.name} → {request.context.proposed_room.name}
          </span></div>
          <p className="admin-request-card__reason">{request.reason}</p>
          {request.decision_note && <p className="muted">Decision: {request.decision_note}</p>}
          {detail ? (
            <StatusHistory request={request} />
          ) : (
            <Link
              className="text-action"
              to={`${rolePath(role, 'request-detail')}?id=${encodeURIComponent(request.id)}`}
            >
              View details for {request.context.class.subject.code}
            </Link>
          )}
          {role === 'administrator' && request.status === 'pending' && (
            <div>
              <RequestPreflight
                requestId={request.id}
                auto={pendingIndex >= 0 && pendingIndex < AUTO_PREFLIGHT_LIMIT}
                refresh={recheck}
                onResult={(result) =>
                  setPreflight((current) => ({ ...current, [request.id]: result }))
                }
              />
              <label htmlFor={`note-${request.id}`}>
                Decision note for {request.context.class.subject.code}
              </label>
              <textarea
                id={`note-${request.id}`}
                maxLength={1000}
                value={notes[request.id] ?? ''}
                onChange={(event) =>
                  setNotes((current) => ({ ...current, [request.id]: event.target.value }))
                }
              />
              <div className="draft-actions">
                <Button
                  loading={busy}
                  disabled={busy || blocked || (notes[request.id]?.trim().length ?? 0) < 3}
                  onClick={() => void decide(request, 'approved')}
                >
                  Approve and publish change
                </Button>
                <Button
                  variant="secondary"
                  disabled={busy || (notes[request.id]?.trim().length ?? 0) < 3}
                  onClick={() => void decide(request, 'rejected')}
                >
                  Decline request
                </Button>
              </div>
            </div>
          )}
          {role === 'administrator' && request.status === 'approved' && (
            <div className="draft-actions">
              {request.draft_id && (
                <Link
                  className="button"
                  to={`/admin/schedule-manager/drafts/${encodeURIComponent(request.draft_id)}?source=academic&request=${request.id}`}
                >
                  Review classroom change
                </Link>
              )}
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => void decide(request, 'fulfilled')}
              >
                Confirm published change
              </Button>
            </div>
          )}
        </article>
        );
      })}
    </section>
  );
}

function CreateClassroomRequest() {
  const workspace = useScheduleWorkspace('teacher');
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [selected, setSelected] = useState(params.get('occurrence') ?? '');
  const event = workspace.records.find((item) => item.id === selected);
  const eventId = event?.id;
  const eventDate = event?.date;
  const [options, setOptions] = useState<{
    publication_id: string;
    rooms: RoomOption[];
  } | null>(null);
  const [room, setRoom] = useState('');
  const [reason, setReason] = useState('');
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [refreshOptions, setRefreshOptions] = useState(0);
  const [conflict, setConflict] = useState('');
  useEffect(() => setConflict(''), [eventId]);
  const available = options?.rooms.filter((item) => item.occupancy !== 'occupied') ?? [];
  useEffect(() => {
    const controller = new AbortController();
    setOptions(null);
    setRoom('');
    setError('');
    setKey(crypto.randomUUID());
    if (eventId && eventDate) {
      const query = new URLSearchParams({
        period_id: workspace.context.period,
        occurrence_id: eventId,
        class_date: eventDate,
      });
      institutionalRequest<{ publication_id: string; rooms: RoomOption[] }>(
        `timetables/requests/options?${query}`,
        { role: 'teacher', signal: controller.signal },
      )
        .then((value) => {
          if (!controller.signal.aborted) setOptions(value);
        })
        .catch((failure) => {
          if (!controller.signal.aborted) setError(failure.message);
        });
    }
    return () => controller.abort();
  }, [eventId, eventDate, workspace.context.period, workspace.data?.version, refreshOptions]);
  const submit = async (submitEvent: FormEvent) => {
    submitEvent.preventDefault();
    if (!event || !options || busy) return;
    setBusy(true);
    setError('');
    try {
      await institutionalRequest('timetables/requests', {
        role: 'teacher',
        method: 'POST',
        body: {
          period_id: workspace.context.period,
          publication_id: options.publication_id,
          occurrence_id: event.id,
          class_date: event.date,
          proposed_room_id: room,
          reason,
          idempotency_key: key,
        },
      });
      navigate('/teacher/change-requests');
    } catch (failure) {
      const message =
        failure instanceof Error
          ? failure.message
          : 'Request submission was not confirmed. Check your requests before retrying.';
      if ((failure as { status?: number }).status === 409) {
        // The room was taken since the options loaded: refresh live occupancy.
        setConflict(message);
        setRefreshOptions((value) => value + 1);
      } else setError(message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="workspace-card" aria-busy={busy}>
      <h1>Request a classroom change</h1>
      <p>
        Your published classroom stays in effect until an Administrator approves the change.
        Approval re-checks conflicts and publishes the new room for you and your students.
      </p>
      <Link to="/teacher/change-requests">Your requests</Link>
      {(error || workspace.error) && <p role="alert">{error || workspace.error}</p>}
      {conflict && !error && <p role="alert">{conflict}</p>}
      {workspace.loading && <ClassSyncSkeleton layout="table" label="Loading your published classes" />}
      <form className="academic-create-period" onSubmit={(event) => void submit(event)}>
        <div>
          <label htmlFor="request-period">Academic period</label>
          <select
            id="request-period"
            value={workspace.context.period}
            onChange={(event) => workspace.change({ period: event.target.value })}
          >
            <option value="">Choose a period</option>
            {workspace.periods.map((period) => (
              <option value={period.id} key={period.id}>
                {periodLabel(period)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="request-date">Show classes from</label>
          <input
            id="request-date"
            type="date"
            value={workspace.date}
            onChange={(event) => workspace.change({ date: event.target.value })}
          />
        </div>
        <div>
          <label htmlFor="request-class">Published class</label>
          <select
            id="request-class"
            required
            value={selected}
            onChange={(event) => setSelected(event.target.value)}
          >
            <option value="">Choose your class</option>
            {workspace.records.map((event) => (
              <option key={event.id} value={event.id}>
                {event.date} · {event.subject.code} · {event.section.name} · {event.room.name}
              </option>
            ))}
          </select>
        </div>
        {!workspace.loading && !workspace.error && workspace.records.length === 0 && (
          <p>No assigned published classes in this date range.</p>
        )}
        {event && !options && !error && <ClassSyncSkeleton rows={2} label="Checking eligible rooms" />}
        {options && (
          <div>
            <label htmlFor="request-room">Proposed classroom</label>
            <select
              id="request-room"
              required
              value={room}
              onChange={(event) => setRoom(event.target.value)}
            >
              <option value="">Choose a classroom</option>
              {options.rooms.map((room) => (
                <option key={room.id} value={room.id} disabled={room.occupancy === 'occupied'}>
                  {room.name}
                  {room.capacity ? ` · ${room.capacity} seats` : ''}
                  {room.occupancy === 'occupied'
                    ? ' · Occupied'
                    : room.occupancy === 'available'
                      ? ' · Available'
                      : ''}
                </option>
              ))}
            </select>
            {options.rooms.length > 0 && (
              <p className="muted" role="status" aria-live="polite">
                {available.length} of {options.rooms.length} eligible rooms are available at this
                class time. Approval re-checks reservations and every scheduling rule.
              </p>
            )}
          </div>
        )}
        {options?.rooms.length === 0 && (
          <p>
            No other eligible classroom is recorded for this published academic scope. Contact your
            Administrator.
          </p>
        )}
        <div>
          <label htmlFor="request-reason">Reason for change</label>
          <textarea
            id="request-reason"
            required
            minLength={3}
            maxLength={1000}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>
        <Button
          type="submit"
          loading={busy}
          disabled={busy || !event || !room || !options || reason.trim().length < 3}
        >
          {busy ? 'Submitting request…' : 'Submit classroom request'}
        </Button>
      </form>
    </section>
  );
}
