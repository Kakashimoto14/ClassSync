import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import { InlineError } from '../components/ui/InlineError';
import { useScheduleWorkspace } from '../lib/use-schedule-workspace';
import { periodLabel } from '../lib/workspace-context';
import {
  issueCategories,
  issueRoom,
  issueStatusLabel,
  issueTime,
  listIssues,
  reportIssue,
  schedulableRooms,
  type FacilityIssue,
  type IssueCategory,
} from '../lib/facility-issues';

export function TeacherIssueReportPage() {
  const workspace = useScheduleWorkspace('teacher');
  const [selected, setSelected] = useState('');
  const [room, setRoom] = useState('');
  const [category, setCategory] = useState<IssueCategory>('equipment');
  const [description, setDescription] = useState('');
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [issues, setIssues] = useState<FacilityIssue[] | null>(null);
  const [listError, setListError] = useState('');
  const [reload, setReload] = useState(0);
  const event = workspace.records.find((item) => item.id === selected);
  const [params] = useSearchParams();
  const requested = params.get('occurrence') ?? '';
  const prefilled = useRef(false);

  // A changed report is a new submission; an unchanged retry keeps its key.
  useEffect(() => setKey(crypto.randomUUID()), [event?.id, room, category, description]);
  useEffect(() => {
    const controller = new AbortController();
    setListError('');
    listIssues('teacher', controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setIssues(value.issues);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setListError(failure.message);
      });
    return () => controller.abort();
  }, [reload]);

  function chooseClass(id: string) {
    setSelected(id);
    const next = workspace.records.find((item) => item.id === id);
    if (next && schedulableRooms.some((item) => item.id === next.room.id)) setRoom(next.room.id);
  }
  // Prefill once, after the classes arrive, and never over a choice already made.
  useEffect(() => {
    if (prefilled.current || !requested) return;
    if (!workspace.records.some((item) => item.id === requested)) return;
    prefilled.current = true;
    if (!selected && !room) chooseClass(requested);
  });
  const requestedMissing =
    Boolean(requested) &&
    !workspace.loading &&
    !workspace.error &&
    !workspace.records.some((item) => item.id === requested);
  async function submit(submitEvent: FormEvent) {
    submitEvent.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await reportIssue({
        id: key,
        room_id: room,
        category,
        description: description.trim(),
        ...(event
          ? {
              period_id: workspace.context.period,
              occurrence_id: event.id,
              occurrence_date: event.date,
            }
          : {}),
      });
      setDescription('');
      setSelected('');
      setNotice('Report sent. An Administrator will review it.');
      setReload((value) => value + 1);
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : 'The report was not confirmed. Check your reports before retrying.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="workspace-card" aria-busy={busy}>
        <p>Reports go to an Administrator. They do not change an official schedule or room.</p>
        {error && <p role="alert">{error}</p>}
        {notice && <p role="status">{notice}</p>}
        {workspace.error && (
          <InlineError
            title="Couldn't load your classes"
            message="You can still report a room."
            onRetry={workspace.retry}
          />
        )}
        {requestedMissing && (
          <p role="status">That class is not in the loaded dates. Choose the class or room below.</p>
        )}
        <form className="academic-create-period" onSubmit={(value) => void submit(value)}>
          <div>
            <label htmlFor="issue-period">Academic period</label>
            <select
              id="issue-period"
              value={workspace.context.period}
              onChange={(e) => workspace.change({ period: e.target.value })}
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
            <label htmlFor="issue-date">Show classes from</label>
            <input
              id="issue-date"
              type="date"
              value={workspace.date}
              onChange={(e) => workspace.change({ date: e.target.value })}
            />
          </div>
          <div>
            <label htmlFor="issue-class">Related class (optional)</label>
            <select id="issue-class" value={selected} onChange={(e) => chooseClass(e.target.value)}>
              <option value="">No specific class</option>
              {workspace.records.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.date} · {item.subject.code} · {item.section.name} · {item.room.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="issue-room">Room</label>
            <select id="issue-room" required value={room} onChange={(e) => setRoom(e.target.value)}>
              <option value="">Choose a room</option>
              {schedulableRooms.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {item.building}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="issue-category">Issue type</label>
            <select
              id="issue-category"
              value={category}
              onChange={(e) => setCategory(e.target.value as IssueCategory)}
            >
              {Object.entries(issueCategories).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="issue-description">Describe the issue</label>
            <textarea
              id="issue-description"
              required
              minLength={3}
              maxLength={2000}
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <Button
            type="submit"
            loading={busy}
            disabled={busy || !room || description.trim().length < 3}
          >
            {busy ? 'Sending report…' : 'Submit report'}
          </Button>
        </form>
      </section>
      <section className="workspace-card" aria-labelledby="own-issues-heading">
        <h2 id="own-issues-heading">Your reports</h2>
        {listError ? (
          <InlineError
            title="Couldn't load your reports"
            message={listError}
            onRetry={() => setReload((value) => value + 1)}
          />
        ) : !issues ? (
          <ClassSyncSkeleton rows={2} label="Loading your reports" />
        ) : issues.length ? (
          <ul>
            {issues.map((issue) => (
              <li key={issue.id}>
                <strong>{issueStatusLabel[issue.status]}</strong> ·{' '}
                {issueRoom(issue.room_id)?.name ?? issue.room_id} ·{' '}
                {issueCategories[issue.category]} · {issueTime(issue.created_at)}
                <p>{issue.description}</p>
                {issue.resolution_note && (
                  <p className="muted">Administrator note: {issue.resolution_note}</p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p>You have not reported any issues.</p>
        )}
      </section>
    </>
  );
}
