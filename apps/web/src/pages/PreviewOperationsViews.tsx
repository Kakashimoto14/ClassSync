import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  previewContext,
  previewProfiles,
  previewResources,
  previewViewer,
  schedulePreview,
} from '../data/schedule-preview';
import {
  formatPreviewDate,
  selectAssignments,
  selectRequests,
  selectUpdates,
} from '../lib/schedule-preview';
import type { UserRole } from '../types/ui';
import { rolePath } from '../routes/route-config';
import { ScheduleAgenda } from '../components/scheduling/ScheduleAgenda';
import { ScheduleEntry } from '../components/scheduling/ScheduleEntry';
import { RequestSummary } from '../components/scheduling/RequestSummary';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { StatusBadge } from '../components/ui/StatusBadge';

// Immediate dashboard destinations share the same fixtures. These views do not
// persist edits, validate constraints, or imply production authorization.
export function PreviewScheduleView({ role }: { role: UserRole }) {
  const [query, setQuery] = useState('');
  const [date, setDate] = useState('all');
  const records = (selectAssignments(schedulePreview, previewViewer(role)) ?? []).filter(
    (item) => role === 'administrator' || item.publication === 'published',
  );
  const dates = [...new Set(records.map((item) => item.startsAt.slice(0, 10)))];
  const filtered = records.filter(
    (item) =>
      (date === 'all' || item.startsAt.startsWith(date)) &&
      [item.subject.name, item.section.name, item.teacher.name, item.room.name]
        .join(' ')
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  );
  return (
    <section className="preview-records">
      <p className="muted">Sample assignments · fixed preview, not an official timetable.</p>
      <div className="screen-toolbar">
        <label>
          Search assignments
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Subject, section, teacher or room"
          />
        </label>
        <label>
          Demo date
          <select value={date} onChange={(event) => setDate(event.target.value)}>
            <option value="all">All supplied dates</option>
            {dates.map((day) => (
              <option key={day} value={day}>
                {formatPreviewDate(day)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {dates
        .filter((day) => filtered.some((item) => item.startsAt.startsWith(day)))
        .map((day) => (
          <ScheduleAgenda
            key={day}
            title={formatPreviewDate(day)}
            occurrences={filtered.filter((item) => item.startsAt.startsWith(day))}
            emptyMessage="No matching assignments"
            showPublication
          />
        ))}
      {!filtered.length && (
        <EmptyState title="No matching assignments" detail="Try another date or search term." />
      )}
      {role === 'teacher' && (
        <Link className="text-action" to={rolePath(role, 'request-create')}>
          Request a room change
        </Link>
      )}
      {role !== 'administrator' && (
        <section className="schedule-export">
          <h2>Export Schedule</h2>
          <Button disabled aria-describedby="preview-export-note">
            Export Schedule
          </Button>
          <p id="preview-export-note">
            Export unavailable: these fictional local dates do not establish an institutional
            timezone or an official schedule.
          </p>
        </section>
      )}
      {role === 'administrator' && (
        <Link className="text-action" to={rolePath(role, 'conflicts')}>
          Review recorded conflicts
        </Link>
      )}
    </section>
  );
}

export function PreviewRequestsView({
  role,
  detail = false,
}: {
  role: 'teacher' | 'administrator';
  detail?: boolean;
}) {
  const [params] = useSearchParams();
  const requests = selectRequests(
    schedulePreview,
    role === 'teacher' ? previewProfiles.teacher.id : undefined,
  ).slice().sort((a,b)=>Number(b.status==='pending')-Number(a.status==='pending'));
  const id = params.get('id');
  const selected = id ? requests.find((item) => item.id === id) : requests[0];
  const shown = detail ? (selected ? [selected] : []) : requests;
  return (
    <section className="preview-records">
      <p className="muted">
        Demonstration requests · separate from your selected timetable. Official changes require
        administrator review.
      </p>
      {shown.map((request) => (
        <RequestSummary
          key={request.id}
          request={request}
          assignment={schedulePreview.occurrences.find((item) => item.id === request.assignmentId)}
          role={role}
          link={!detail}
        />
      ))}
      {!shown.length && (
        <EmptyState
          title="Request unavailable"
          detail="The requested record is not in this role’s preview."
        />
      )}
      {detail && selected && role === 'administrator' && selected.status === 'pending' && (
        <>
          <Alert tone="info" title="Decisions unavailable">
            Approval and rejection require connected scheduling services.
          </Alert>
          <div className="inline-actions">
            <Button disabled>Approve request</Button>
            <Button variant="secondary" disabled>
              Decline request
            </Button>
          </div>
        </>
      )}
      <nav className="dashboard-actions" aria-label="Request actions">
        {detail && (
          <Link className="text-action" to={rolePath(role, 'requests')}>
            Back to requests
          </Link>
        )}
        {role === 'teacher' && (
          <Link className="text-action" to={rolePath(role, 'request-create')}>
            New room change request
          </Link>
        )}
      </nav>
    </section>
  );
}

export function PreviewConflictView({ detail = false }: { detail?: boolean }) {
  const [params] = useSearchParams();
  const [query, setQuery] = useState('');
  const id = params.get('id');
  const records = schedulePreview.conflicts.filter((item) => item.status === 'open');
  const selected = id ? records.find((item) => item.id === id) : records[0];
  const shown = (detail ? (selected ? [selected] : []) : records).filter((item) =>
    (
      item.reason +
      item.assignmentIds
        .map((assignmentId) => {
          const assignment = schedulePreview.occurrences.find(
            (record) => record.id === assignmentId,
          );
          return assignment
            ? [
                assignment.subject.name,
                assignment.section.name,
                assignment.teacher.name,
                assignment.room.name,
              ].join(' ')
            : '';
        })
        .join(' ')
    )
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );
  return (
    <section className="preview-records">
      <p className="muted">Recorded demo issues · not live conflict detection.</p>
      {!detail && (
        <label>
          Search conflicts
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Subject, section, teacher or room"
          />
        </label>
      )}
      {shown.map((conflict) => (
        <article className="dashboard-panel" key={conflict.id}>
          <StatusBadge tone="danger">Blocking conflict</StatusBadge>
          <h2>Overlapping room assignments</h2>
          <p>{conflict.reason}</p>
          {conflict.assignmentIds.map((assignmentId) => {
            const assignment = schedulePreview.occurrences.find((item) => item.id === assignmentId);
            return assignment ? (
              <ScheduleEntry key={assignmentId} occurrence={assignment} showDate showPublication />
            ) : (
              <p key={assignmentId}>Assignment unavailable</p>
            );
          })}
          {!detail && (
            <Link
              className="text-action"
              to={`${rolePath('administrator', 'conflict-detail')}?id=${encodeURIComponent(conflict.id)}`}
            >
              View conflict details
            </Link>
          )}
        </article>
      ))}
      {!shown.length && (
        <EmptyState
          title={detail ? 'Conflict unavailable' : 'No matching recorded conflicts'}
          detail="This is not a live validation or clearance result."
        />
      )}
      <nav className="dashboard-actions" aria-label="Conflict actions">
        {detail && (
          <Link className="text-action" to={rolePath('administrator', 'conflicts')}>
            Back to Conflict Center
          </Link>
        )}
        <Link className="text-action" to={rolePath('administrator', 'schedule-manager')}>
          Open Schedule Manager
        </Link>
        <Link className="text-action" to={rolePath('administrator', 'availability')}>
          Review classroom resources
        </Link>
      </nav>
    </section>
  );
}

export function PreviewRequestCreateView() {
  const assignments = (selectAssignments(schedulePreview, previewViewer('teacher')) ?? []).filter(
    (item) => item.publication === 'published' && item.endsAt > previewContext.reference,
  );
  return (
    <section className="workspace-card request-form">
      <Alert tone="info" title="Request submission unavailable">
        This preview does not send requests or change official schedules.
      </Alert>
      <label>
        Assigned class
        <select defaultValue="">
          <option value="" disabled>
            Select an assignment
          </option>
          {assignments.map((item) => (
            <option key={item.id} value={item.id}>
              {item.subject.name} · {item.section.name} · {formatPreviewDate(item.startsAt)}{' '}
              {item.startsAt.slice(11, 16)} · {item.room.name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Suggested room
        <select defaultValue="">
          <option value="">No room preference</option>
          {previewResources.map((room) => (
            <option key={room.id} value={room.id} disabled={room.condition === 'maintenance'}>
              {room.name} · {room.seats} seats ·{' '}
              {room.condition === 'maintenance' ? 'Maintenance' : 'Resource active'}
            </option>
          ))}
        </select>
      </label>
      <p className="muted">Availability and suitability must be validated before any change.</p>
      <label>
        Reason
        <textarea rows={4} placeholder="Explain the requested change." />
      </label>
      <div className="inline-actions">
        <Link className="button button--secondary" to={rolePath('teacher', 'requests')}>
          Back to requests
        </Link>
        <Button disabled>Submit request</Button>
      </div>
    </section>
  );
}

export function PreviewUpdatesView({ role }: { role: UserRole }) {
  const assignments = selectAssignments(schedulePreview, previewViewer(role)) ?? [];
  const updates = selectUpdates(schedulePreview, assignments);
  return (
    <section className="preview-records">
      <p className="muted">
        Demonstration alerts · separate from your selected timetable. Notification delivery is not
        connected.
      </p>
      {updates.map((update) => (
        <article key={update.id} className="dashboard-panel">
          <h2>{update.title}</h2>
          <p>{update.detail}</p>
        </article>
      ))}
      {!updates.length && (
        <EmptyState
          title="No sample updates"
          detail="There are no updates for these assignments."
        />
      )}
      <Link
        className="text-action"
        to={rolePath(role, role === 'administrator' ? 'schedule-manager' : 'schedule')}
      >
        Open{' '}
        {role === 'administrator'
          ? 'Schedule Manager'
          : role === 'teacher'
            ? 'teaching schedule'
            : 'my schedule'}
      </Link>
    </section>
  );
}
