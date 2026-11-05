import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { institutionalRequest } from '../lib/institutional-api';
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

export function ClassroomRequestsPage({ role, create = false }: { role: Role; create?: boolean }) {
  const [requests, setRequests] = useState<ClassroomRequest[] | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (create) return;
    const controller = new AbortController();
    setRequests(null);
    setError('');
    institutionalRequest<{ requests: ClassroomRequest[] }>('timetables/requests', {
      role,
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted) setRequests(data.requests);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setError(failure.message);
      });
    return () => controller.abort();
  }, [role, reload, create]);
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
      setNotice(stateLabel[updated.status]);
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : 'The decision was not confirmed. Reload and retry.',
      );
    } finally {
      setBusy(false);
    }
  };
  if (create) return <CreateClassroomRequest />;
  return (
    <section className="workspace-card" aria-busy={busy}>
      <h1>Classroom requests</h1>
      <p>
        {role === 'teacher'
          ? 'Track requests for your published classes.'
          : 'Review faculty requests. Classroom changes take effect only after validated publication.'}
      </p>
      <div className="draft-actions">
        {role === 'teacher' && (
          <Link className="button" to="/teacher/change-requests/new">
            Request a classroom change
          </Link>
        )}
        <Button variant="secondary" onClick={() => setReload((value) => value + 1)} disabled={busy}>
          Reload requests
        </Button>
      </div>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!requests && !error && <p role="status">Loading classroom requests…</p>}
      {requests?.length === 0 && <p>No classroom requests yet.</p>}
      {requests?.map((request) => (
        <article className="workspace-card" key={request.id}>
          <h2>
            {request.context.class.subject.code} · {request.context.class.subject.name}
          </h2>
          <p>
            {request.context.class.date} · {request.context.class.section.name}
          </p>
          <p>
            {request.context.class.room.name} → {request.context.proposed_room.name}
          </p>
          <p>
            <strong>{stateLabel[request.status]}</strong>
          </p>
          <p>{request.reason}</p>
          {request.decision_note && <p>Decision: {request.decision_note}</p>}
          {role === 'administrator' && request.status === 'pending' && (
            <div>
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
                  disabled={busy || (notes[request.id]?.trim().length ?? 0) < 3}
                  onClick={() => void decide(request, 'approved')}
                >
                  Approve for publication
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
      ))}
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
    rooms: Array<{ id: string; name: string }>;
  } | null>(null);
  const [room, setRoom] = useState('');
  const [reason, setReason] = useState('');
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
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
      institutionalRequest<{ publication_id: string; rooms: Array<{ id: string; name: string }> }>(
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
  }, [eventId, eventDate, workspace.context.period, workspace.data?.version]);
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
      setError(
        failure instanceof Error
          ? failure.message
          : 'Request submission was not confirmed. Check your requests before retrying.',
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="workspace-card" aria-busy={busy}>
      <h1>Request a classroom change</h1>
      <p>
        Your published classroom stays in effect until an Administrator reviews and publishes a
        validated change.
      </p>
      <Link to="/teacher/change-requests">Your requests</Link>
      {(error || workspace.error) && <p role="alert">{error || workspace.error}</p>}
      {workspace.loading && <p role="status">Loading your published classes…</p>}
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
        {event && !options && !error && <p role="status">Checking eligible rooms…</p>}
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
                <option key={room.id} value={room.id}>
                  {room.name}
                </option>
              ))}
            </select>
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
          disabled={busy || !event || !room || !options || reason.trim().length < 3}
        >
          {busy ? 'Submitting request…' : 'Submit classroom request'}
        </Button>
      </form>
    </section>
  );
}
