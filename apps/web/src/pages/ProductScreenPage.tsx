import { presentationOnlyBuild } from '../lib/presentation-sample';
import { PresentationConflictSummary } from '../components/scheduling/PresentationConflictSummary';
import { useState } from 'react';
import { previewViewer, schedulePreview } from '../data/schedule-preview';
import { selectAssignments } from '../lib/schedule-preview';
import {
  PreviewRequestsView,
  PreviewRequestCreateView,
  PreviewUpdatesView,
} from './PreviewOperationsViews';
import { CalendarDays, FileBarChart, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { RoomDiscoveryPage, RoomDetailPage } from './RoomDiscoveryPages';
import { PreviewBuildingDirectory, PreviewBuildingDetail } from './PreviewBuildingViews';
import { SchedulingSourcePage } from './AcademicGenerationPage';
import { AcademicManagementPage } from './AcademicManagementPage';
import { SavedDraftsPage, SavedDraftDetailPage } from './SchedulingDraftPages';
import { ConflictCenterPage } from './ConflictCenterPage';
import { PublicationAuditPage } from './PublicationAuditPage';
import { StructuredCalendarPage } from './StructuredCalendarPage';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { EmptyState } from '../components/ui/EmptyState';
import { StatusBadge } from '../components/ui/StatusBadge';
import { rolePath, type RouteDefinition } from '../routes/route-config';

export function ProductScreenPage({ definition }: { definition: RouteDefinition }) {
  if (
    presentationOnlyBuild &&
    definition.role === 'administrator' &&
    [
      'schedule',
      'schedule-create',
      'academic-list',
      'academic-detail',
      'schedule-drafts',
      'schedule-draft-detail',
      'academic-manage',
      'conflicts',
      'conflict-detail',
      'audit',
    ].includes(definition.kind)
  )
    return (
      <AppShell>
        <section className="workspace-card">
          <h1>Read-only presentation</h1>
          {definition.kind === 'conflicts' && <PresentationConflictSummary />}
          <p>
            This tool needs the connected backend and verified Administrator access. Generation,
            editing, validation, saving and publishing are unavailable in this presentation.
          </p>
          <Link className="button button--secondary" to="/admin/calendar">
            Review sample timetable
          </Link>
        </section>
      </AppShell>
    );
  if (definition.kind === 'rooms')
    return (
      <AppShell>
        <RoomDiscoveryPage key={definition.id} definition={definition} />
      </AppShell>
    );
  if (definition.kind === 'room-detail')
    return (
      <AppShell>
        <RoomDetailPage role={definition.role} />
      </AppShell>
    );
  const compactHeading = [
    'reports',
    'schedule-create',
    'schedule',
    'calendar',
    'notifications',
    'buildings',
    'building-detail',
  ].includes(definition.kind);
  return (
    <AppShell>
      <div className="page-heading">
        <div>
          {!compactHeading && (
            <p className="eyebrow">
              {definition.navigationGroup ??
                (definition.role === 'administrator' ? 'Administrator' : definition.role)}
            </p>
          )}
          <h1>{definition.title}</h1>
          {!compactHeading && <p>{definition.description}</p>}
        </div>
        {definition.kind === 'schedule' && definition.role === 'administrator' && (
          <Link className="button" to="/admin/schedule-manager/create">
            Generate Weekly Schedule
          </Link>
        )}
      </div>
      {definition.kind === 'schedule' &&
        (definition.role === 'administrator' ? (
          <section className="workspace-card">
            <h2>Schedule review</h2>
            <p>
              Generate from academic data, save a draft, then revalidate its scope before
              publication.
            </p>
            <Link className="text-action" to="/admin/calendar">
              Published Timetables
            </Link>
          </section>
        ) : (
          <StructuredCalendarPage role={definition.role} />
        ))}
      {definition.kind === 'schedule-create' && <CreateScheduleScreen />}
      {definition.kind === 'academic-manage' && (
        <AcademicManagementPage initialKind={definition.academicKind} />
      )}
      {definition.kind === 'schedule' && definition.role === 'administrator' && (
        <div className="draft-actions">
          <Link className="text-action" to="/admin/schedule-manager/drafts">
            Saved Drafts
          </Link>
          <Link className="text-action" to="/admin/academic">
            Manage Academic Data
          </Link>
        </div>
      )}
      {definition.kind === 'schedule-drafts' && <SavedDraftsPage />}
      {definition.kind === 'schedule-draft-detail' && <SavedDraftDetailPage />}
      {definition.kind === 'calendar' && <StructuredCalendarPage role={definition.role} />}
      {definition.kind === 'conflicts' && <ConflictScreen />}
      {definition.kind === 'conflict-detail' && <ConflictDetailScreen />}
      {definition.kind === 'requests' && <RequestScreen role={definition.role} />}
      {definition.kind === 'request-create' && <RequestCreateScreen />}
      {definition.kind === 'request-detail' && <RequestDetailScreen role={definition.role} />}
      {definition.kind === 'report-issue' && <IssueReportScreen />}
      {definition.kind === 'buildings' && <PreviewBuildingDirectory />}
      {definition.kind === 'building-detail' && <PreviewBuildingDetail />}
      {definition.kind === 'academic-list' && <AcademicListScreen definition={definition} />}
      {definition.kind === 'academic-detail' && <AcademicDetailScreen />}
      {definition.kind === 'reports' && (
        <ReportScreen utilization={definition.id.endsWith('.utilization')} />
      )}
      {definition.kind === 'notifications' && <PreviewUpdatesView role={definition.role} />}
      {definition.kind === 'announcements' && <AnnouncementScreen role={definition.role} />}
      {definition.kind === 'profile' && <ProfileScreen role={definition.role} />}
      {definition.kind === 'settings' && <SettingsScreen />}
      {definition.kind === 'audit' && <AuditScreen />}
    </AppShell>
  );
}

function CreateScheduleScreen() {
  return <SchedulingSourcePage />;
}

function ConflictScreen() {
  return <ConflictCenterPage />;
}
function ConflictDetailScreen() {
  return <ConflictCenterPage />;
}

function RequestScreen({ role }: { role: RouteDefinition['role'] }) {
  return role === 'student' ? null : <PreviewRequestsView role={role} />;
}

function RequestCreateScreen() {
  return <PreviewRequestCreateView />;
}

function RequestDetailScreen({ role }: { role: RouteDefinition['role'] }) {
  return role === 'student' ? null : <PreviewRequestsView role={role} detail />;
}

function IssueReportScreen() {
  return (
    <form className="workspace-card request-form" onSubmit={(event) => event.preventDefault()}>
      <h2>Classroom or schedule issue</h2>
      <p className="muted">
        Reports go to an administrator. They do not change an official schedule.
      </p>
      <label>
        Related class
        <select defaultValue="">
          <option value="" disabled>
            Select a class
          </option>
          {(selectAssignments(schedulePreview, previewViewer('teacher')) ?? [])
            .filter((item) => item.publication === 'published')
            .map((item) => (
              <option key={item.id} value={item.id}>
                {item.subject.name} · {item.startsAt.slice(0, 10)} {item.startsAt.slice(11, 16)} ·{' '}
                {item.room.name}
              </option>
            ))}
        </select>
      </label>
      <label>
        Issue type
        <select defaultValue="room">
          <option value="room">Classroom issue</option>
          <option value="schedule">Schedule conflict</option>
        </select>
      </label>
      <label>
        Describe the issue
        <textarea
          required
          rows={4}
          placeholder="Include the room, time, and what needs attention."
        />
      </label>
      <Button type="submit" disabled>
        Submit report
      </Button>
    </form>
  );
}

function AcademicListScreen({ definition }: { definition: RouteDefinition }) {
  const subject = definition.title === 'Subjects';
  const group = definition.title === 'Sections';
  const firstColumn = subject ? 'Subject' : group ? 'Section' : definition.title.slice(0, -1);
  const rows = subject
    ? ['Database Management Systems', 'Web Systems', 'Human Computer Interaction']
    : group
      ? ['BSIT 2A', 'BSCS 1B', 'BSIT 3A']
      : ['Avery Cruz', 'Morgan Reyes', 'Sam Lee'];
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const displayedRows = rows.filter(
    (name, index) =>
      name.toLowerCase().includes(query.trim().toLowerCase()) &&
      (status === 'all' || (status === 'attention' ? index === 1 : index !== 1)),
  );
  return (
    <>
      <div className="screen-toolbar">
        <label>
          <Search size={16} />
          <input
            placeholder={`Search ${definition.title.toLowerCase()}`}
            aria-label={`Search ${definition.title.toLowerCase()}`}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <label>
          Status
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="attention">Attention</option>
          </select>
        </label>
      </div>
      {displayedRows.length > 0 ? (
        <>
          <section className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{firstColumn}</th>
                  <th>{subject ? 'Code' : group ? 'Program · Year' : 'Academic context'}</th>
                  <th>Status</th>
                  <th>Schedule relation</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {displayedRows.map((name) => {
                  const index = rows.indexOf(name);
                  return (
                    <tr key={name}>
                      <td>
                        <strong>{name}</strong>
                      </td>
                      <td>
                        {subject
                          ? `SUB-${201 + index}`
                          : group
                            ? 'BSIT · Year 2'
                            : 'Academic scheduling'}
                      </td>
                      <td>
                        <StatusBadge tone={index === 1 ? 'warning' : 'success'}>
                          {index === 1 ? 'Attention' : 'Active'}
                        </StatusBadge>
                      </td>
                      <td>{index + 1} assigned classes</td>
                      <td>
                        <Link className="text-action" to="/admin/academic/details">
                          View record
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
          <div className="mobile-record-list">
            {displayedRows.map((name) => {
              const index = rows.indexOf(name);
              return (
                <article key={name}>
                  <strong>{name}</strong>
                  <span>{subject ? `SUB-${201 + index}` : 'Academic scheduling'}</span>
                  <StatusBadge tone={index === 1 ? 'warning' : 'success'}>
                    {index === 1 ? 'Attention' : 'Active'}
                  </StatusBadge>
                </article>
              );
            })}
          </div>
        </>
      ) : (
        <EmptyState
          title={`No matching ${definition.title.toLowerCase()}`}
          detail="Try another search term or status."
        />
      )}
    </>
  );
}
function AcademicDetailScreen() {
  return (
    <section className="workspace-card">
      <p className="eyebrow">Academic record</p>
      <h2>BSIT 2A · Second Year</h2>
      <dl className="detail-list">
        <dt>Program</dt>
        <dd>Bachelor of Science in Information Technology</dd>
        <dt>Students</dt>
        <dd>35 active students</dd>
        <dt>Adviser</dt>
        <dd>Prof. Maria Santos</dd>
        <dt>Schedule</dt>
        <dd>Published · 18 class periods</dd>
      </dl>
      <h3>Related subjects</h3>
      <ul className="related-list">
        <li>Database Management Systems</li>
        <li>Web Systems</li>
        <li>Human Computer Interaction</li>
      </ul>
    </section>
  );
}

function ReportScreen({ utilization }: { utilization: boolean }) {
  return (
    <section className="workspace-card">
      <FileBarChart aria-hidden="true" />
      <h2>{utilization ? 'Room utilization reports' : 'Scheduling reports'} · Coming soon</h2>
      <p>
        Operational reports need connected, authorized academic and published timetable data. No
        campus metrics are available here.
      </p>
      <Link className="button button--secondary" to="/admin/calendar">
        Review timetable data
      </Link>
    </section>
  );
}

function AnnouncementScreen({ role }: { role: RouteDefinition['role'] }) {
  return (
    <section className="notice-list">
      {[
        'Academic schedule release',
        'Classroom maintenance notice',
        'Semester timetable reminder',
      ].map((title, index) => (
        <article key={title}>
          <span className="notice-icon">
            <CalendarDays />
          </span>
          <div>
            <StatusBadge tone="info">{index === 0 ? 'Academic' : 'Room'}</StatusBadge>
            <h2>{title}</h2>
            <p>Information relevant to current classroom schedules and availability.</p>
            <small>{index + 1} days ago</small>
          </div>
          {role === 'administrator' && (
            <span className="status status--neutral">Editing unavailable</span>
          )}
        </article>
      ))}
    </section>
  );
}

function ProfileScreen({ role }: { role: RouteDefinition['role'] }) {
  const data =
    role === 'student'
      ? ['Maria Santos', 'Student', 'BSIT 2A · Second Year']
      : role === 'teacher'
        ? ['Prof. Santos', 'Teacher', 'Information Technology']
        : ['Admin User', 'Administrator', 'Academic Operations'];
  return (
    <section className="workspace-card profile-card">
      <span className="avatar profile-avatar">
        {data[0]
          .split(' ')
          .map((part) => part[0])
          .join('')}
      </span>
      <div>
        <p className="eyebrow">{data[1]}</p>
        <h2>{data[0]}</h2>
        <p>{data[2]}</p>
      </div>
      <dl className="detail-list">
        <dt>Account</dt>
        <dd>University account</dd>
        <dt>Schedule access</dt>
        <dd>
          {role === 'student'
            ? 'Published schedules'
            : role === 'teacher'
              ? 'Assigned teaching schedules'
              : 'Scheduling administration'}
        </dd>
      </dl>
      <Link className="button button--secondary" to={rolePath(role, 'settings')}>
        Account settings
      </Link>
    </section>
  );
}

function SettingsScreen() {
  return (
    <section className="workspace-card settings-card">
      <h2>Preferences</h2>
      <Alert tone="info" title="Settings preview">
        Notification preferences are shown for interface review only; this local demo does not save
        account settings.
      </Alert>
      <div className="settings-row">
        <div>
          <strong>Schedule notifications</strong>
          <p>Receive updates about room and time changes.</p>
        </div>
        <input
          type="checkbox"
          checked
          readOnly
          disabled
          aria-label="Schedule notifications unavailable in this preview"
        />
      </div>
      <div className="settings-row">
        <div>
          <strong>Announcement notifications</strong>
          <p>Receive important university scheduling notices.</p>
        </div>
        <input
          type="checkbox"
          checked
          readOnly
          disabled
          aria-label="Announcement notifications unavailable in this preview"
        />
      </div>
      <div className="settings-row">
        <div>
          <strong>Account security</strong>
          <p>Production sign-in and account security are not configured in this local demo.</p>
        </div>
        <span className="status status--neutral">Development preview</span>
      </div>
    </section>
  );
}

function AuditScreen() {
  return <PublicationAuditPage />;
}
