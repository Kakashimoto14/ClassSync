import { useState, type FormEvent } from 'react';
import { Button } from '../ui/Button';
import { institutionalRequest } from '../../lib/institutional-api';
import type { UserRole } from '../../types/ui';

type SlotRoom = {
  id: string;
  name: string;
  building: string | null;
  floor: string | null;
  occupancy: 'free' | 'occupied' | 'restricted';
};
type SlotResult = {
  restrictions_checked: boolean;
  rooms: SlotRoom[];
  start: number;
  end: number;
};
type Filter = 'all' | 'free' | 'occupied';

const label = { free: 'No class', occupied: 'Occupied', restricted: 'Reserved' } as const;
// 07:00–21:00 in 30-minute steps, matching scheduler slot alignment.
const times = Array.from({ length: 29 }, (_, index) => 420 + index * 30);
const clock = (minute: number) =>
  `${String(Math.floor(minute / 60)).padStart(2, '0')}:${String(minute % 60).padStart(2, '0')}`;

/** Live occupancy of all schedulable campus rooms for one published time slot. */
export function RoomSlotChecker({
  role,
  period,
  initialDate,
}: {
  role: UserRole;
  period: string;
  initialDate: string;
}) {
  const [day, setDay] = useState(initialDate);
  const [start, setStart] = useState(480);
  const [end, setEnd] = useState(570);
  const [filter, setFilter] = useState<Filter>('all');
  const [result, setResult] = useState<SlotResult | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const check = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || !period || end <= start) return;
    setBusy(true);
    setError('');
    try {
      const query = new URLSearchParams({ date: day, start: String(start), end: String(end) });
      const value = await institutionalRequest<SlotResult>(
        `timetables/rooms/${encodeURIComponent(period)}/slot?${query}`,
        { role, timeout: 20000 },
      );
      // Label results with the slot that was actually queried, not later select changes.
      setResult({ ...value, start, end });
    } catch (failure) {
      setResult(null);
      setError(failure instanceof Error ? failure.message : 'Room availability is unavailable.');
    } finally {
      setBusy(false);
    }
  };
  const free = result?.rooms.filter((room) => room.occupancy === 'free') ?? [];
  const shown =
    result?.rooms.filter((room) =>
      filter === 'all' ? true : filter === 'free' ? room.occupancy === 'free' : room.occupancy !== 'free',
    ) ?? [];
  return (
    <section className="room-slot-checker workspace-card" aria-labelledby="room-slot-heading">
      <h2 id="room-slot-heading">Check room availability</h2>
      <form className="room-slot-form" onSubmit={(event) => void check(event)}>
        <label>
          Date
          <input type="date" required value={day} onChange={(e) => setDay(e.target.value)} />
        </label>
        <label>
          From
          <select
            value={start}
            onChange={(e) => {
              const next = Number(e.target.value);
              setStart(next);
              if (end <= next) setEnd(next + 30);
            }}
          >
            {times.slice(0, -1).map((minute) => (
              <option key={minute} value={minute}>
                {clock(minute)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Until
          <select value={end} onChange={(e) => setEnd(Number(e.target.value))}>
            {times.slice(1).map((minute) => (
              <option key={minute} value={minute} disabled={minute <= start}>
                {clock(minute)}
              </option>
            ))}
          </select>
        </label>
        <Button type="submit" loading={busy} disabled={busy || !period || end <= start}>
          {busy ? 'Checking rooms…' : 'Check rooms'}
        </Button>
      </form>
      {error && <p role="alert">{error}</p>}
      {result && (
        <>
          <p role="status" aria-live="polite">
            {free.length} of {result.rooms.length} rooms have no published class from{' '}
            {clock(result.start)} to {clock(result.end)}.
            {!result.restrictions_checked &&
              ' Reservations are confirmed by an Administrator when a change is approved.'}
          </p>
          <div className="admin-filter-pills" role="group" aria-label="Filter rooms by availability">
            {(['all', 'free', 'occupied'] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-pressed={filter === value}
                onClick={() => setFilter(value)}
              >
                {value === 'all' ? 'All' : value === 'free' ? 'No class' : 'Occupied'}
              </button>
            ))}
          </div>
          <ul className="room-slot-list">
            {shown.map((room) => (
              <li key={room.id} className={`room-slot room-slot--${room.occupancy}`}>
                <strong>{room.name}</strong>
                <span>
                  {room.building ?? 'Building unavailable'}
                  {room.floor ? ` · Floor ${room.floor}` : ''}
                </span>
                <span className="room-slot__state">{label[room.occupancy]}</span>
              </li>
            ))}
          </ul>
          {!shown.length && <p>No rooms match this filter.</p>}
        </>
      )}
    </section>
  );
}
