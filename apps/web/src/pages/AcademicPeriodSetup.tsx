import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import type { AcademicKind, AcademicSnapshot } from '../lib/academic-api';
import { academicLabel, academicPath, academicTabs } from '../lib/academic-labels';
import { periodLabel } from '../lib/workspace-context';
import { AcademicCalendarEditor } from './AcademicCalendarEditor';
import { AcademicRecordEditor } from './AcademicRecordEditor';
import { suppliedAcademicProgramCatalog } from '../data/academic-program-catalog';

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
  editing,
  editingKind,
  onEdit,
  onCancel,
  onSaved,
  onReload,
}: {
  snapshot: AcademicSnapshot;
  editing: string | null;
  editingKind: AcademicKind;
  onEdit: (kind: AcademicKind, id: string) => void;
  onCancel: () => void;
  onSaved: (next: AcademicSnapshot) => void;
  onReload: () => void;
}) {
  const [activeKind, setActiveKind] = useState<AcademicKind>('programs');
  const populatedAreas = academicTabs.filter((tab) =>
    snapshot.records.some((entry) => entry.record.kind === tab.kind),
  ).length;
  const startedAreas = populatedAreas + Number(Boolean(snapshot.period.calendar));

  return (
    <section className="academic-setup" aria-labelledby="academic-setup-title">
      <header className="academic-setup__header">
        <div>
          <p className="academic-setup__eyebrow">Academic period setup</p>
          <h2 id="academic-setup-title">Set up {periodLabel(snapshot.period)}</h2>
          <p>
            Enter approved records from one workspace. Each save is confirmed separately, so you can
            pause and continue later.
          </p>
        </div>
        <StatusBadge tone="neutral">{`Revision ${snapshot.period.revision}`}</StatusBadge>
      </header>

      <div className="academic-setup__progress" role="status">
        <strong>{startedAreas} of 8 setup areas have saved information</strong>
        <span>
          This counts saved records only. It does not certify source accuracy or scheduling
          readiness.
        </span>
      </div>

      <details className="academic-setup__calendar" open={!snapshot.period.calendar}>
        <summary>Calendar setup</summary>
        <AcademicCalendarEditor snapshot={snapshot} onSaved={onSaved} open={!snapshot.period.calendar} />
      </details>

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
