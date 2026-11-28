import { useEffect, useState } from 'react';
import { Button } from '../ui/Button';
import type { CalendarRange } from '../../lib/calendar-ics';
import type { CalendarOccurrence } from '../../lib/calendar-model';
import type { UserRole } from '../../types/ui';

export function ExportIcsButton({
  records,
  role,
  view,
  date,
}: {
  records: readonly CalendarOccurrence[];
  role: UserRole;
  view: CalendarRange;
  date: string;
}) {
  const [message, setMessage] = useState('');
  useEffect(() => setMessage(''), [view, date]);
  async function save() {
    try {
      const { exportSchedule } = await import('../../lib/calendar-ics');
      const count = exportSchedule(records, role, view, date);
      setMessage(
        count
          ? `Calendar file prepared with ${count} ${count === 1 ? 'class' : 'classes'}.`
          : `No classes in this ${view} to export.`,
      );
    } catch {
      setMessage('The calendar file could not be prepared. Try again.');
    }
  }
  return (
    <div className="draft-actions">
      <Button variant="secondary" onClick={() => void save()}>
        Export .ics ({view})
      </Button>
      <span aria-live="polite">{message}</span>
    </div>
  );
}
