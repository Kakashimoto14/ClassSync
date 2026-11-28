import { useState, type FormEvent } from 'react';
import { archiveAcademicPeriod, cloneAcademicPeriod } from '../lib/admin-operations-api';
import type { AcademicPeriod } from '../lib/academic-api';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';

export function PeriodLifecycleControls({
  period,
  onCloned,
  onArchived,
}: {
  period: AcademicPeriod;
  onCloned: (periodId: string) => void;
  onArchived: () => void;
}) {
  const [dialog, setDialog] = useState<'clone' | 'archive' | null>(null);
  const [title, setTitle] = useState(`${period.title} (copy)`.slice(0, 160));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      await action();
      setDialog(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The period could not be changed.');
    } finally {
      setBusy(false);
    }
  }
  const clone = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      const saved = await cloneAcademicPeriod(period.id, title.trim());
      onCloned(saved.period.id);
    });
  };
  const archive = () =>
    void run(async () => {
      await archiveAcademicPeriod(period.id, period.revision);
      onArchived();
    });
  const close = () => {
    if (!busy) {
      setDialog(null);
      setError('');
    }
  };

  return (
    <div className="draft-actions" aria-label="Period lifecycle">
      {period.archived_at && (
        <p role="status">This period is archived and read-only. Clone it to make changes.</p>
      )}
      <Button variant="secondary" onClick={() => setDialog('clone')}>Clone period</Button>
      {!period.archived_at && (
        <Button variant="ghost" className="quiet-danger" onClick={() => setDialog('archive')}>Archive period</Button>
      )}
      {dialog === 'clone' && (
        <Modal title="Clone academic period" onClose={close}>
          <form className="modal-body" onSubmit={clone}>
            <p>
              Copies programs, subjects, sections, faculty, rooms, offerings, scheduling rules and
              the calendar dates. Student enrollments, locked classes, holidays, term phases, drafts
              and published timetables are not copied. Review the dates before using the copy.
            </p>
            <label>
              New period title
              <input required maxLength={160} value={title} onChange={(event) => setTitle(event.target.value)} />
            </label>
            {error && <p role="alert" className="scheduler-error">{error}</p>}
            <div className="modal-actions">
              <Button type="button" variant="secondary" disabled={busy} onClick={close}>Cancel</Button>
              <Button type="submit" loading={busy} disabled={busy || !title.trim()}>Create copy</Button>
            </div>
          </form>
        </Modal>
      )}
      {dialog === 'archive' && (
        <Modal title="Archive academic period" onClose={close}>
          <div className="modal-body">
            <p>
              Archive “{period.title}”? This is permanent: it cannot be undone. Records, calendar,
              roster and drafts become read-only, nothing more can be published, and the period
              leaves the working period lists. A timetable already published stays visible and
              keeps its rooms booked until its end date. The period can still be cloned.
            </p>
            {error && <p role="alert" className="scheduler-error">{error}</p>}
            <div className="modal-actions">
              <Button type="button" variant="secondary" disabled={busy} onClick={close}>Keep period</Button>
              <Button type="button" variant="danger" loading={busy} disabled={busy} onClick={archive}>
                Archive permanently
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
