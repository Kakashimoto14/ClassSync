import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { ClassSyncSkeleton } from '../components/loading/ClassSyncLoading';
import { InlineError } from '../components/ui/InlineError';
import { StatusBadge } from '../components/ui/StatusBadge';
import { listRestrictions, type SavedRestriction } from '../lib/admin-operations-api';
import { rolePath } from '../routes/route-config';
import {
  issueCategories,
  issueRoom,
  issueStatusLabel,
  issueTime,
  listIssues,
  transitionIssue,
  type FacilityIssue,
  type IssueStatus,
} from '../lib/facility-issues';

const issueTone = {
  open: 'warning',
  in_progress: 'info',
  resolved: 'success',
  dismissed: 'neutral',
} as const;

function restrictionPath(issue: FacilityIssue) {
  const room = issueRoom(issue.room_id);
  if (!room) return rolePath('administrator', 'buildings');
  const query = new URLSearchParams({
    building: room.building,
    room: room.id,
    restrict: '1',
    reason: `Reported ${issueCategories[issue.category].toLowerCase()} issue`,
  });
  return `${rolePath('administrator', 'building-detail')}?${query}`;
}

export function IssueTriagePanel() {
  const [issues, setIssues] = useState<FacilityIssue[] | null>(null);
  const [restrictions, setRestrictions] = useState<SavedRestriction[]>([]);
  const [restrictionError, setRestrictionError] = useState(false);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [links, setLinks] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIssues(null);
    setLoadError('');
    listIssues('administrator', controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setIssues(value.issues);
      })
      .catch((failure) => {
        if (!controller.signal.aborted) setLoadError(failure.message);
      });
    setRestrictionError(false);
    listRestrictions()
      .then((value) => {
        if (!controller.signal.aborted) setRestrictions(value.restrictions);
      })
      .catch(() => {
        if (!controller.signal.aborted) setRestrictionError(true);
      });
    return () => controller.abort();
  }, [reload]);

  function refresh() {
    setError('');
    setReload((value) => value + 1);
  }
  async function update(issue: FacilityIssue, status: Exclude<IssueStatus, 'open'>) {
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    const note = notes[issue.id]?.trim();
    try {
      await transitionIssue(issue.id, {
        expected_revision: issue.revision,
        status,
        ...(note ? { note } : {}),
        ...(links[issue.id] ? { linked_restriction_id: links[issue.id] } : {}),
      });
      setNotes((current) => ({ ...current, [issue.id]: '' }));
      setNotice(`Report marked ${issueStatusLabel[status].toLowerCase()}.`);
      setReload((value) => value + 1);
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : 'The update was not confirmed. Reload.',
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="triage" aria-busy={busy}>
      <div className="admin-screen-actions admin-requests-actions">
        <Button variant="secondary" disabled={busy} onClick={refresh}>
          Reload issue reports
        </Button>
      </div>
      {loadError && (
        <InlineError title="Couldn't load issue reports" message={loadError} onRetry={refresh} />
      )}
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {restrictionError && (
        <InlineError
          title="Couldn't load room restrictions"
          message="Reports stay readable, but no restriction can be linked yet."
          onRetry={refresh}
        />
      )}
      {!issues && !loadError && <ClassSyncSkeleton layout="rows" label="Loading issue reports" />}
      {issues?.length === 0 && <p className="workspace-card admin-empty">No issue reports yet.</p>}
      {issues?.map((issue) => {
        const room = issueRoom(issue.room_id)?.name ?? issue.room_id;
        const open = issue.status === 'open' || issue.status === 'in_progress';
        const note = notes[issue.id]?.trim() ?? '';
        const linkable = restrictions.filter(
          (item) => item.room_id === issue.room_id && item.status === 'active',
        );
        const badNote = note.length > 0 && note.length < 3;
        const noClose = busy || badNote || (!note && !issue.resolution_note);
        return (
          <article className="workspace-card admin-request-card" key={issue.id}>
            <header className="admin-request-card__header">
              <div>
                <StatusBadge tone={issueTone[issue.status]}>
                  {issueStatusLabel[issue.status]}
                </StatusBadge>
                <h2>
                  {room} · {issueCategories[issue.category]}
                </h2>
              </div>
              <span className="admin-request-card__date">{issueTime(issue.created_at)}</span>
            </header>
            {issue.occurrence_date && (
              <p className="muted">Reported for the class on {issue.occurrence_date}</p>
            )}
            <p className="admin-request-card__reason">{issue.description}</p>
            {issue.resolution_note && <p className="muted">Note: {issue.resolution_note}</p>}
            {issue.linked_restriction_id && (
              <p className="muted">A room restriction is linked to this report.</p>
            )}
            {!!issue.history?.length && (
              <details>
                <summary>Status history</summary>
                <ol>
                  {issue.history.map((event) => (
                    <li key={event.revision}>
                      {issueStatusLabel[event.to_status]} · {issueTime(event.created_at)}
                    </li>
                  ))}
                </ol>
              </details>
            )}
            {open && (
              <div>
                <label htmlFor={`issue-note-${issue.id}`}>Note for {room}</label>
                <textarea
                  id={`issue-note-${issue.id}`}
                  maxLength={1000}
                  value={notes[issue.id] ?? ''}
                  onChange={(e) =>
                    setNotes((current) => ({ ...current, [issue.id]: e.target.value }))
                  }
                />
                <label htmlFor={`issue-link-${issue.id}`}>Linked restriction (optional)</label>
                <select
                  id={`issue-link-${issue.id}`}
                  value={links[issue.id] ?? ''}
                  onChange={(e) =>
                    setLinks((current) => ({ ...current, [issue.id]: e.target.value }))
                  }
                >
                  <option value="">None</option>
                  {linkable.map((item) => (
                    <option key={item.id} value={item.id}>
                      {issueTime(item.starts_at)} to {issueTime(item.ends_at)} · {item.reason}
                    </option>
                  ))}
                </select>
                <Link className="button button--secondary triage-issue-link" to={restrictionPath(issue)}>
                  Add a restriction for {room}
                </Link>
                <div className="draft-actions">
                  {issue.status === 'open' && (
                    <Button
                      variant="secondary"
                      disabled={busy || badNote}
                      onClick={() => void update(issue, 'in_progress')}
                    >
                      Start work
                    </Button>
                  )}
                  <Button variant="secondary" disabled={noClose} onClick={() => void update(issue, 'resolved')}>
                    Mark resolved
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={noClose}
                    onClick={() => void update(issue, 'dismissed')}
                  >
                    Dismiss report
                  </Button>
                </div>
                <p className="muted">Resolving or dismissing needs a note.</p>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
