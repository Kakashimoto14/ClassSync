import { useState, type FormEvent } from 'react';
import { timetableRequest } from '../lib/publication-api';
import { schedulingSandboxEnabled } from '../lib/scheduling-api';
import { Button } from '../components/ui/Button';
import { readWorkspace } from '../lib/workspace-context';
import type { UserRole } from '../types/ui';
import { manilaToday } from '../lib/calendar-model';
export function PublishedRoomAvailability({
  rooms,
  role = 'student',
}: {
  role?: UserRole;
  rooms: Array<{ id: string; name: string }>;
}) {
  const [room, setRoom] = useState(rooms[0]?.id ?? '');
  const [date, setDate] = useState(() => readWorkspace(role).date || manilaToday());
  const [start, setStart] = useState('09:00');
  const [end, setEnd] = useState('10:00');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      const query = new URLSearchParams({
        room_id: room,
        start: `${date}T${start}:00+08:00`,
        end: `${date}T${end}:00+08:00`,
      });
      const value = await timetableRequest<{
        occupancy: string;
        suitability: string;
        sessions: number;
      }>((schedulingSandboxEnabled ? 'sandbox/' : '') + 'availability?' + query);
      setMessage(
        `Published occupancy: ${value.occupancy}. ${value.sessions} overlapping sessions. Capacity/equipment suitability remains ${value.suitability}.`,
      );
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Availability not confirmed');
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="workspace-card">
      <summary>Check published room occupancy</summary>
      <form className="academic-create-period" onSubmit={submit}>
        <p>
          {schedulingSandboxEnabled ? 'Synthetic published scope' : 'University published scope'} ·
          Asia/Manila · Unpublished drafts are excluded.
        </p>
        <label>
          Room
          <select value={room} onChange={(e) => setRoom(e.target.value)}>
            {rooms.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Date
          <input type="date" value={date} required onChange={(e) => setDate(e.target.value)} />
        </label>
        <label>
          From
          <input type="time" value={start} required onChange={(e) => setStart(e.target.value)} />
        </label>
        <label>
          Until
          <input type="time" value={end} required onChange={(e) => setEnd(e.target.value)} />
        </label>
        <Button disabled={busy || !room}>{busy ? 'Checking…' : 'Check occupancy'}</Button>
        <p role="status">{message}</p>
      </form>
    </details>
  );
}
