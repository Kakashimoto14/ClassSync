import { useState } from 'react';
import { Button } from '../components/ui/Button';
import type { DraftDetail } from '../lib/scheduling-api';
type Exception = {
  date: string;
  reason: string;
  assignment_id: string | null;
  cancelled: boolean;
  moved_to?: string | null;
  room_id?: string | null;
  start?: number | null;
};
export function OccurrenceExceptionEditor({
  draft,
  start,
  exceptions,
  onChange,
  disabled,
}: {
  draft: DraftDetail;
  start: string;
  exceptions: Exception[];
  onChange: (value: Exception[]) => void;
  disabled: boolean;
}) {
  const [date, setDate] = useState(start);
  const [assignment, setAssignment] = useState('');
  const [reason, setReason] = useState('');
  const [action, setAction] = useState('cancel');
  const [moved, setMoved] = useState(start);
  const [room, setRoom] = useState(draft.input_snapshot.rooms?.[0]?.id ?? '');
  const [time, setTime] = useState('09:00');
  const valid =
    !!date &&
    !!reason.trim() &&
    (action !== 'move' || (!!assignment && !!moved && !!room && !!time));
  return (
    <details>
      <summary>Holidays and occurrence changes</summary>
      <div className="academic-create-period">
        <label>
          Original class date
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            disabled={disabled}
          />
        </label>
        <label>
          Affected session
          <select
            value={assignment}
            onChange={(e) => setAssignment(e.target.value)}
            disabled={disabled}
          >
            <option value="">All classes on this date (holiday)</option>
            {draft.generation_result.assignments.map((a) => (
              <option key={a.id} value={a.id}>
                {draft.input_snapshot.offerings?.find((o) => o.id === a.offering_id)?.subject_name}{' '}
                · weekly day {a.day + 1} · {Math.floor(a.start / 60)}:
                {String(a.start % 60).padStart(2, '0')}
              </option>
            ))}
          </select>
        </label>
        <label>
          Change
          <select value={action} onChange={(e) => setAction(e.target.value)} disabled={disabled}>
            <option value="cancel">Cancel / holiday</option>
            <option value="move">Move a single occurrence</option>
          </select>
        </label>
        {action === 'move' && (
          <>
            <label>
              Revised date
              <input
                type="date"
                value={moved}
                onChange={(e) => setMoved(e.target.value)}
                disabled={disabled}
              />
            </label>
            <label>
              Revised start
              <input
                type="time"
                step="1800"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                disabled={disabled}
              />
            </label>
            <label>
              Revised room
              <select value={room} onChange={(e) => setRoom(e.target.value)} disabled={disabled}>
                {draft.input_snapshot.rooms?.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}
        <label>
          Reason
          <input
            maxLength={200}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={disabled}
          />
        </label>
        <Button
          variant="secondary"
          disabled={disabled || !valid}
          onClick={() => {
            const [h, m] = time.split(':').map(Number);
            onChange([
              ...exceptions,
              {
                date,
                reason: reason.trim(),
                assignment_id: assignment || null,
                cancelled: action === 'cancel',
                ...(action === 'move' ? { moved_to: moved, room_id: room, start: h * 60 + m } : {}),
              },
            ]);
            setReason('');
          }}
        >
          Add reviewed exception
        </Button>
        <ul>
          {exceptions.map((e, i) => (
            <li key={i}>
              {e.date} · {e.reason}
              <Button
                variant="ghost"
                disabled={disabled}
                onClick={() => onChange(exceptions.filter((_, n) => i !== n))}
              >
                Remove exception
              </Button>
            </li>
          ))}
        </ul>
      </div>
    </details>
  );
}
