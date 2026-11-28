import { useEffect, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  listRestrictions,
  preflightRestriction,
  saveRestriction,
  type RestrictionImpact,
  type SavedRestriction,
} from '../lib/admin-operations-api';
import { provisionalCdmRooms } from '../data/cdm-room-inventory';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import { InlineError } from '../components/ui/InlineError';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import { rolePath } from '../routes/route-config';
import './admin-operations.css';

const buildings = [...new Set(provisionalCdmRooms.map((room) => room.building))].sort();
const roomName = (id: string) => provisionalCdmRooms.find((room) => room.id === id)?.name ?? id;

// Campus times are Manila time (UTC+08:00, no daylight saving).
const toCampus = (local: string) => `${local}:00+08:00`;
const toLocalInput = (value: string) =>
  new Date(new Date(value).getTime() + 8 * 3600_000).toISOString().slice(0, 16);
const readable = (value: string) => toLocalInput(value).replace('T', ' ');

interface Draft {
  id: string;
  revision: number;
  room_id: string;
  starts: string;
  ends: string;
  kind: 'operational' | 'reservation';
  reason: string;
}

const newDraft = (roomId: string, reason = ''): Draft => ({
  id: crypto.randomUUID(), revision: 0, room_id: roomId,
  starts: '', ends: '', kind: 'operational', reason,
});

export function BuildingsPage({ detail = false }: { detail?: boolean }) {
  const [params] = useSearchParams();
  const building = params.get('building') ?? '';
  const selectedRoom = params.get('room') ?? '';
  const [restrictions, setRestrictions] = useState<SavedRestriction[] | null>(null);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [notice, setNotice] = useState('');
  const [attempt, setAttempt] = useState(0);
  // A facility issue link opens a prefilled form; saving still needs the usual check.
  const [draft, setDraft] = useState<Draft | null>(() =>
    params.get('restrict') === '1' &&
    provisionalCdmRooms.some(
      (room) => room.id === selectedRoom && room.schedulable && room.building === building,
    )
      ? newDraft(selectedRoom, (params.get('reason') ?? '').slice(0, 200))
      : null,
  );
  const [impact, setImpact] = useState<RestrictionImpact | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let ignore = false;
    setLoadError('');
    listRestrictions()
      .then((result) => { if (!ignore) setRestrictions(result.restrictions); })
      .catch((cause: unknown) => {
        if (!ignore) setLoadError(cause instanceof Error ? cause.message : 'Restrictions could not be loaded.');
      });
    return () => { ignore = true; };
  }, [attempt]);

  const rooms = provisionalCdmRooms.filter((room) => room.building === building);
  const schedulable = rooms.filter((room) => room.schedulable);
  const excluded = rooms.filter((room) => !room.schedulable);
  const roomIds = new Set(schedulable.map((room) => room.id));
  const shown = (restrictions ?? []).filter(
    (item) => roomIds.has(item.room_id) && (!selectedRoom || item.room_id === selectedRoom),
  );
  const activeFor = (id: string) =>
    (restrictions ?? []).filter((item) => item.room_id === id && item.status === 'active').length;

  function change(next: Partial<Draft>) {
    setDraft((current) => (current ? { ...current, ...next } : current));
    setImpact(null);
  }
  function open(item?: SavedRestriction, roomId = selectedRoom || schedulable[0]?.id || '') {
    setError('');
    setNotice('');
    setImpact(null);
    setDraft(
      item
        ? {
            id: item.id, revision: item.revision, room_id: item.room_id,
            starts: toLocalInput(item.starts_at), ends: toLocalInput(item.ends_at),
            kind: item.kind, reason: item.reason,
          }
        : newDraft(roomId),
    );
  }
  const command = (value: Draft) => ({
    id: value.id,
    room_id: value.room_id,
    dataset: 'institutional' as const,
    starts_at: toCampus(value.starts),
    ends_at: toCampus(value.ends),
    kind: value.kind,
    reason: value.reason.trim(),
    expected_revision: value.revision,
    status: 'active' as const,
  });
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The restriction could not be saved.');
    } finally {
      setBusy(false);
    }
  }
  function check(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    if (draft.starts >= draft.ends) {
      setError('The end must be after the start.');
      return;
    }
    void run(async () => setImpact(await preflightRestriction(command(draft))));
  }
  const save = () =>
    run(async () => {
      if (!draft) return;
      await saveRestriction(command(draft));
      setDraft(null);
      setImpact(null);
      setNotice('Restriction saved.');
      setAttempt((value) => value + 1);
    });
  const cancel = (item: SavedRestriction) => {
    if (!window.confirm(`Cancel the restriction on ${roomName(item.room_id)}? The room becomes bookable again.`))
      return;
    void run(async () => {
      await saveRestriction({
        id: item.id, room_id: item.room_id, dataset: item.dataset, starts_at: item.starts_at,
        ends_at: item.ends_at, kind: item.kind, reason: item.reason,
        expected_revision: item.revision, status: 'cancelled',
      });
      setNotice('Restriction cancelled.');
      setDraft(null);
      setAttempt((value) => value + 1);
    });
  };

  const readFailure = loadError && (
    <InlineError
      title="Couldn't load room restrictions"
      message={loadError}
      onRetry={() => setAttempt((value) => value + 1)}
    />
  );

  if (!detail)
    return (
      <div className="admin-ops">
        <p className="muted">
          {provisionalCdmRooms.filter((room) => room.schedulable).length} schedulable rooms and{' '}
          {provisionalCdmRooms.filter((room) => !room.schedulable).length} excluded spaces from the
          supplied campus inventory. Physical condition is not verified.
        </p>
        {readFailure}
        <div className="admin-ops__grid">
          {buildings.map((name) => {
            const members = provisionalCdmRooms.filter((room) => room.building === name);
            const active = members.reduce((sum, room) => sum + activeFor(room.id), 0);
            return (
              <article className="workspace-card" key={name}>
                <h2>{name}</h2>
                <p>
                  {members.filter((room) => room.schedulable).length} schedulable ·{' '}
                  {members.filter((room) => !room.schedulable).length} excluded
                </p>
                <p className="muted">
                  {restrictions === null ? 'Restrictions not loaded' : `${active} active restrictions`}
                </p>
                <Link
                  className="text-action"
                  to={`${rolePath('administrator', 'building-detail')}?building=${encodeURIComponent(name)}`}
                >
                  Open {name}
                </Link>
              </article>
            );
          })}
        </div>
      </div>
    );

  return (
    <div className="admin-ops">
      <Link className="text-action" to={rolePath('administrator', 'buildings')}>Back to buildings</Link>
      {!rooms.length ? (
        <p>Choose a building from the directory.</p>
      ) : (
        <>
          {notice && <p role="status">{notice}</p>}
          {readFailure}
          {error && <p role="alert" className="scheduler-error">{error}</p>}
          <section className="workspace-card" aria-label="Schedulable rooms">
            <h2>{building}: {schedulable.length} schedulable rooms</h2>
            {schedulable.length ? (
              <ul className="admin-ops__list">
                {schedulable.map((room) => (
                  <li key={room.id}>
                    <strong>{room.name}</strong>
                    <span className="muted">
                      {room.floor ?? 'Floor not recorded'} · {activeFor(room.id)} active restrictions
                    </span>
                    <div className="admin-ops__actions">
                      <Link
                        className="text-action"
                        aria-current={selectedRoom === room.id ? 'true' : undefined}
                        to={`${rolePath('administrator', 'building-detail')}?building=${encodeURIComponent(building)}&room=${encodeURIComponent(room.id)}`}
                      >
                        Show {room.name} restrictions
                      </Link>
                      <Button variant="secondary" disabled={busy} onClick={() => open(undefined, room.id)}>
                        Restrict {room.name}
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No schedulable rooms in this building.</p>
            )}
          </section>
          {draft && (
            <form className="workspace-card" aria-label="Room restriction" onSubmit={check}>
              <h2>{draft.revision ? 'Edit restriction' : 'New restriction'}</h2>
              <div className="admin-ops__form">
                <label>
                  Room
                  <select required value={draft.room_id} onChange={(event) => change({ room_id: event.target.value })}>
                    {schedulable.map((room) => <option key={room.id} value={room.id}>{room.name}</option>)}
                  </select>
                </label>
                <label>
                  Starts (campus time)
                  <input required type="datetime-local" value={draft.starts} onChange={(event) => change({ starts: event.target.value })} />
                </label>
                <label>
                  Ends (campus time)
                  <input required type="datetime-local" value={draft.ends} onChange={(event) => change({ ends: event.target.value })} />
                </label>
                <label>
                  Type
                  <select value={draft.kind} onChange={(event) => change({ kind: event.target.value as Draft['kind'] })}>
                    <option value="operational">Maintenance or closure</option>
                    <option value="reservation">Reservation</option>
                  </select>
                </label>
                <label>
                  Reason
                  <input required maxLength={200} value={draft.reason} onChange={(event) => change({ reason: event.target.value })} />
                </label>
              </div>
              {impact && (
                <div role="status">
                  {impact.total === 0 ? (
                    <p>No published class is affected.</p>
                  ) : (
                    <>
                      <p>
                        {impact.total} published class meetings overlap. Move or cancel them before
                        saving this restriction.
                      </p>
                      <ul>
                        {impact.sessions.slice(0, 10).map((session) => (
                          <li key={`${session.starts_at}-${session.section.name}`}>
                            {session.date} {session.starts_at.slice(11, 16)}–{session.ends_at.slice(11, 16)} ·{' '}
                            {session.subject.code} · {session.section.name} · {session.teacher.name}
                          </li>
                        ))}
                      </ul>
                      {impact.total > 10 && <p className="muted">Showing 10 of {impact.total}.</p>}
                    </>
                  )}
                </div>
              )}
              <div className="admin-ops__actions">
                <Button type="submit" variant="secondary" disabled={busy || !draft.reason.trim()}>
                  Check affected classes
                </Button>
                <Button type="button" loading={busy} disabled={busy || impact?.total !== 0} onClick={() => void save()}>
                  Save restriction
                </Button>
                <Button type="button" variant="ghost" disabled={busy} onClick={() => setDraft(null)}>
                  Close
                </Button>
              </div>
            </form>
          )}
          <section className="workspace-card" aria-label="Dated restrictions">
            <div className="admin-ops__bar">
              <h2>Dated restrictions{selectedRoom ? ` · ${roomName(selectedRoom)}` : ''}</h2>
              <Button disabled={busy || !schedulable.length} onClick={() => open()}>Add restriction</Button>
            </div>
            {restrictions === null && !loadError && <ClassSyncSkeleton label="Loading restrictions" />}
            {restrictions !== null && !shown.length && <p className="muted">No restrictions recorded.</p>}
            <ul className="admin-ops__list">
              {shown.map((item) => (
                <li key={item.id}>
                  <strong>{roomName(item.room_id)}</strong>
                  <StatusBadge tone={item.status === 'active' ? 'warning' : 'neutral'}>
                    {item.status === 'active' ? 'Active' : 'Cancelled'}
                  </StatusBadge>
                  <span>{readable(item.starts_at)} to {readable(item.ends_at)}</span>
                  <span className="muted">{item.reason}</span>
                  {item.status === 'active' && (
                    <div className="admin-ops__actions">
                      <Button variant="secondary" disabled={busy} onClick={() => open(item)}>
                        Edit {roomName(item.room_id)} restriction
                      </Button>
                      <Button variant="danger" disabled={busy} onClick={() => cancel(item)}>
                        Cancel {roomName(item.room_id)} restriction
                      </Button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </section>
          <section className="workspace-card" aria-label="Excluded spaces">
            <h2>{excluded.length} excluded spaces</h2>
            <p className="muted">These spaces are never scheduled and cannot be restricted or booked.</p>
            <ul>{excluded.map((room) => <li key={room.id}>{room.name}</li>)}</ul>
          </section>
        </>
      )}
    </div>
  );
}
