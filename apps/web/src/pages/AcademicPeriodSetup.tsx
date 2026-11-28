import { lazy, Suspense, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import type { AcademicKind, AcademicReadiness, AcademicRecord, AcademicSnapshot } from '../lib/academic-api';
import { academicLabel, academicPath, academicTabs } from '../lib/academic-labels';
import { periodLabel } from '../lib/workspace-context';
import { AcademicCalendarEditor } from './AcademicCalendarEditor';
import { AcademicRecordEditor } from './AcademicRecordEditor';
import { suppliedAcademicProgramCatalog } from '../data/academic-program-catalog';
import { appMode } from '../config/runtime-config';

const PeriodLifecycleControls = lazy(() =>
  import('./PeriodLifecycleControls').then((module) => ({ default: module.PeriodLifecycleControls })),
);

const setupDescriptions: Record<AcademicKind, string> = {
  programs: 'Review the supplied program list and naming rules for this period.',
  subjects: 'Select curriculum courses, then enter approved weekly contact minutes.',
  sections: 'Choose a program, year level and section letter from menus.',
  faculty: 'Add assigned faculty and enter their confirmed availability.',
  offerings: 'Connect each confirmed subject and section to faculty and suitable rooms.',
  resources: 'Review the supplied spaces and add verified operational details.',
  constraints: 'Set approved teaching days, time windows and scope confirmations.',
};

const addLabels: Record<AcademicKind, string> = {
  programs: 'Add program',
  subjects: 'Add subject',
  sections: 'Add section',
  faculty: 'Add faculty',
  offerings: 'Add subject offering',
  resources: 'Add resource',
  constraints: 'Configure scheduling rules',
};

function recordSummary(record: AcademicSnapshot['records'][number]['record']): string {
  if (record.kind === 'subjects') {
    return `${record.required_weekly_minutes ?? 'Minutes missing'} weekly minutes · ${record.patterns?.length ?? 0} allowed patterns`;
  }
  if (record.kind === 'sections') {
    return `Year ${record.year_level ?? '—'} · Section ${record.section_letter ?? record.custom_label ?? '—'}`;
  }
  if (record.kind === 'faculty') {
    return `${record.subject_ids?.length ?? 0} subjects · ${record.availability?.length ?? 0} availability windows`;
  }
  if (record.kind === 'offerings') {
    return `${record.teacher_ids?.length ?? 0} faculty · ${record.room_ids?.length ?? 0} room choices`;
  }
  if (record.kind === 'resources') {
    return record.condition === 'operational' && record.type_verified
      ? 'Room type and operational status verified'
      : 'Room verification still required';
  }
  if (record.kind === 'constraints') {
    return `${record.operating_windows?.length ?? 0} operating windows`;
  }
  if (record.kind === 'programs') return record.institute;
  return '';
}

export function AcademicPeriodSetup({
  snapshot,
  readiness,
  editing,
  editingKind,
  onEdit,
  onCancel,
  onSaved,
  onReload,
  onCloned,
  note,
  periodControls,
  actions,
  notices,
}: {
  snapshot: AcademicSnapshot;
  readiness?: AcademicReadiness | null;
  editing: string | null;
  editingKind: AcademicKind;
  onEdit: (kind: AcademicKind, id: string) => void;
  onCancel: () => void;
  onSaved: (next: AcademicSnapshot) => void;
  onReload: () => void;
  onCloned?: (periodId: string) => void;
  note?: string;
  periodControls?: ReactNode;
  actions?: ReactNode;
  notices?: ReactNode;
}) {
  const [activeKind, setActiveKind] = useState<AcademicKind>('programs');
  const records = <Kind extends AcademicKind>(kind: Kind): Extract<AcademicRecord, { kind: Kind }>[] =>
    snapshot.records
      .filter((entry) => entry.record.kind === kind)
      .map((entry) => entry.record as Extract<AcademicRecord, { kind: Kind }>);
  const constraints = records('constraints').find((record) => record.kind === 'constraints');
  const programs = records('programs');
  const subjects = records('subjects').filter((record) => record.kind === 'subjects');
  const sections = records('sections').filter((record) => record.kind === 'sections');
  const faculty = records('faculty').filter((record) => record.kind === 'faculty');
  const resources = records('resources').filter((record) => record.kind === 'resources');
  const offerings = records('offerings').filter((record) => record.kind === 'offerings');
  const rosterCount = constraints?.enrollments?.length ?? 0;
  const steps = [
    {
      title: 'Academic Period & Scheduling Constraints',
      kind: 'constraints' as const,
      count: `${snapshot.period.calendar ? 'Calendar saved' : 'Calendar missing'} · ${records('constraints').length} rule set`,
      started: Boolean(snapshot.period.calendar || records('constraints').length),
      ready: Boolean(snapshot.period.calendar && constraints?.kind === 'constraints' && constraints.operating_windows_verified && constraints.shared_scope_verified),
      detail: 'Set the approved calendar, operating windows, transition time, and shared-scope references.',
    },
    {
      title: 'Programs & Curriculum Subjects',
      kind: 'subjects' as const,
      count: `${programs.length} programs · ${subjects.length} subjects`,
      started: programs.length + subjects.length > 0,
      ready: programs.length > 0 && subjects.length > 0 && subjects.every((subject) => subject.curriculum_review_verified && subject.contact_minutes_verified),
      detail: 'Review the editable program catalog and enter subjects from approved curriculum sources.',
    },
    {
      title: 'Sections & Student Roster',
      kind: 'sections' as const,
      count: `${sections.length} sections · ${rosterCount} students`,
      started: sections.length > 0,
      ready: sections.length > 0 && sections.every((section) => section.identity_verified && section.cohort_assignment_verified && section.population_verified && (section.population ?? 0) > 0),
      detail: 'Set up sections by year; student enrollment uses the verified roster onboarding process.',
    },
    {
      title: 'Faculty & Availability',
      kind: 'faculty' as const,
      count: `${faculty.length} faculty records`,
      started: faculty.length > 0,
      ready: faculty.length > 0 && faculty.every((member) => member.eligibility_verified && member.availability_verified && member.workload_verified),
      detail: 'Record verified subject eligibility, workload limits, and weekly availability.',
    },
    {
      title: 'Campus Rooms & Resource Metadata',
      kind: 'resources' as const,
      count: `${resources.length} room records`,
      started: resources.length > 0,
      ready: resources.length > 0 && resources.every((room) => room.condition === 'operational' && room.schedulable && room.type_verified && room.capacity_verified && room.availability_verified),
      detail: 'Review each room’s verified type, capacity, operational condition, and availability.',
    },
    {
      title: 'Subject Offerings & Schedule Generation',
      kind: 'offerings' as const,
      count: `${offerings.length} offerings`,
      started: offerings.length > 0,
      ready: offerings.length > 0 && offerings.every((offering) => offering.term_offering_verified) && readiness?.ready === true,
      detail: 'Confirm term offerings, then validate readiness before generating a schedule draft.',
    },
  ];

  const startedSteps = steps.filter((step) => step.started).length;
  const calendarSetup = (
    <details className="academic-setup__calendar" open={!snapshot.period.calendar}>
      <summary>Calendar setup</summary>
      <AcademicCalendarEditor snapshot={snapshot} onSaved={onSaved} open={!snapshot.period.calendar} />
    </details>
  );

  return (
    <section className="academic-setup" aria-labelledby="academic-setup-title">
      <header className="academic-setup__header">
        <div className="academic-setup__title">
          <h2 id="academic-setup-title">Set up {periodLabel(snapshot.period)}</h2>
          <p className="academic-setup__meta">
            <StatusBadge tone="neutral">{`Revision ${snapshot.period.revision}`}</StatusBadge>
            {note && <span>{note}</span>}
          </p>
        </div>
        {periodControls}
        {actions}
        <div className="academic-setup__progress">
          <strong role="status">
            {startedSteps} of {steps.length} setup steps have saved information
          </strong>
          <progress value={startedSteps} max={steps.length} aria-label="Setup progress" />
          <span>
            This counts saved records only. It does not certify source accuracy or scheduling
            readiness.
          </span>
        </div>
      </header>
      {notices}

      {!snapshot.period.calendar && calendarSetup}

      <ol className="academic-setup__steps" aria-label="Six setup steps">
        {steps.map((step, index) => {
          const count = records(step.kind).length;
          const status = step.ready ? 'Ready' : step.started ? 'In progress' : 'Not started';
          return (
            <li
              className={`academic-setup__step${step.ready ? ' academic-setup__step--ready' : ''}`}
              key={step.title}
            >
              <div className="academic-setup__step-heading">
                <span className="academic-setup__step-number">{index + 1}</span>
                <StatusBadge tone={step.ready ? 'success' : count ? 'info' : 'warning'}>{status}</StatusBadge>
              </div>
              <h3>{step.title}</h3>
              <p>{step.detail}</p>
              <p className="academic-setup__step-count">{step.count}</p>
              <Link className="button button--secondary" to={academicPath(step.kind, snapshot.period.id)}>
                {count ? 'Manage' : 'Set up'} <span aria-hidden="true">→</span>
              </Link>
            </li>
          );
        })}
      </ol>

      {snapshot.period.calendar && calendarSetup}

      {appMode === 'institutional' && onCloned && (
        <Suspense fallback={null}>
          <PeriodLifecycleControls
            key={snapshot.period.id}
            period={snapshot.period}
            onCloned={onCloned}
            onArchived={onReload}
          />
        </Suspense>
      )}

      <nav className="academic-setup__jump" aria-label="Academic setup areas">
        {academicTabs.map((tab) => (
          <button
            key={tab.kind}
            type="button"
            aria-pressed={activeKind === tab.kind}
            onClick={() => setActiveKind(tab.kind)}
          >
            <span>{tab.label}</span>
            <StatusBadge tone={snapshot.records.some((entry) => entry.record.kind === tab.kind) ? 'neutral' : 'warning'}>{String(snapshot.records.filter((entry) => entry.record.kind === tab.kind).length)}</StatusBadge>
          </button>
        ))}
      </nav>

      <div className="academic-setup__grid">
        {academicTabs.filter((tab) => tab.kind === activeKind).map((tab) => {
          const entries = snapshot.records.filter((entry) => entry.record.kind === tab.kind);
          const currentEditor = editing !== null && editingKind === tab.kind;
          const allCatalogProgramsSaved =
            tab.kind === 'programs' &&
            suppliedAcademicProgramCatalog.every((program) =>
              entries.some((entry) => entry.record.id === program.id),
            );
          const existing = entries.find((entry) => entry.record.id === editing);
          return (
            <section
              className={`academic-setup-card${currentEditor ? ' academic-setup-card--editing' : ''}`}
              id={`setup-${tab.kind}`}
              key={tab.kind}
              aria-labelledby={`setup-${tab.kind}-title`}
            >
              <header className="academic-setup-card__header">
                <div>
                  <p className="academic-setup-card__eyebrow">Setup area</p>
                  <h3 id={`setup-${tab.kind}-title`}>{tab.label}</h3>
                  <p>{setupDescriptions[tab.kind]}</p>
                </div>
                <StatusBadge tone={entries.length ? 'neutral' : 'warning'}>
                  {entries.length ? `${entries.length} saved` : 'Needs setup'}
                </StatusBadge>
              </header>

              {currentEditor ? (
                <AcademicRecordEditor
                  key={`${snapshot.period.id}:${tab.kind}:${editing}`}
                  kind={tab.kind}
                  snapshot={snapshot}
                  existing={existing}
                  onCancel={onCancel}
                  onReload={onReload}
                  onSaved={onSaved}
                />
              ) : (
                <>
                  {entries.length ? (
                    <ul className="academic-setup-card__records">
                      {entries.slice(0, 3).map((entry) => (
                        <li key={entry.record.id}>
                          <div>
                            <strong>
                              {academicLabel(
                                entry.record as Parameters<typeof academicLabel>[0],
                                snapshot,
                              )}
                            </strong>
                            <span>{recordSummary(entry.record)}</span>
                          </div>
                          <Button
                            variant="secondary"
                            onClick={() => onEdit(tab.kind, entry.record.id!)}
                            aria-label={`Edit ${academicLabel(entry.record as Parameters<typeof academicLabel>[0], snapshot)}`}
                          >
                            Edit
                          </Button>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="academic-setup-card__empty">No records saved for this area.</p>
                  )}
                  <div className="academic-setup-card__actions">
                    <Button
                      disabled={allCatalogProgramsSaved}
                      onClick={() =>
                        onEdit(
                          tab.kind,
                          tab.kind === 'constraints' && entries[0] ? entries[0].record.id! : 'new',
                        )
                      }
                    >
                      {allCatalogProgramsSaved
                        ? 'All supplied programs added'
                        : tab.kind === 'constraints' && entries.length
                          ? 'Edit scheduling rules'
                          : addLabels[tab.kind]}
                    </Button>
                    <Link
                      className="button button--secondary"
                      to={academicPath(tab.kind, snapshot.period.id)}
                    >
                      View all {tab.label.toLowerCase()}
                    </Link>
                  </div>
                </>
              )}
            </section>
          );
        })}
      </div>
    </section>
  );
}
