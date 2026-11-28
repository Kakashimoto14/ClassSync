import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/StatusBadge';
import { DataTable, type Column } from '../components/ui/DataTable';
import type { AcademicKind, AcademicRecord, AcademicSnapshot } from '../lib/academic-api';
import { academicLabel, academicRecords } from '../lib/academic-labels';

type Entry = AcademicSnapshot['records'][number];
type Of<Kind extends AcademicKind> = Extract<AcademicRecord, { kind: Kind }>;

const title = (main: string, note?: string) => (
  <span>
    <span className="cell-title">{main}</span>
    {note && <span className="cell-note">{note}</span>}
  </span>
);
const text = (header: string, cell: (record: AcademicRecord) => string, nowrap = false) => ({
  header,
  className: nowrap ? 'nowrap' : undefined,
  cell: (entry: Entry) => <span>{cell(entry.record as AcademicRecord)}</span>,
});
const count = (header: string, cell: (record: AcademicRecord) => string | number) => ({
  header,
  numeric: true,
  cell: (entry: Entry) => <span>{cell(entry.record as AcademicRecord)}</span>,
});

function columnsFor(kind: AcademicKind, snapshot: AcademicSnapshot): Column<Entry>[] {
  const programs = academicRecords(snapshot, 'programs') as Of<'programs'>[];
  const subjects = academicRecords(snapshot, 'subjects') as Of<'subjects'>[];
  const sections = academicRecords(snapshot, 'sections') as Of<'sections'>[];
  const acronym = (id: string) => programs.find((p) => p.id === id)?.acronym ?? id.toUpperCase();
  switch (kind) {
    case 'programs':
      return [
        text('Program', (r) => (r as Of<'programs'>).acronym, true),
        { header: 'Name', cell: (e) => <span className="cell-title">{(e.record as Of<'programs'>).name}</span> },
        text('Institute', (r) => (r as Of<'programs'>).institute),
      ];
    case 'subjects':
      return [
        text('Code', (r) => (r as Of<'subjects'>).code, true),
        { header: 'Subject', cell: (e) => <span className="cell-title">{(e.record as Of<'subjects'>).name}</span> },
        count('Year', (r) => (r as Of<'subjects'>).year_level ?? '—'),
        count('Weekly minutes', (r) => (r as Of<'subjects'>).required_weekly_minutes ?? 'Missing'),
        count('Patterns', (r) => (r as Of<'subjects'>).patterns?.length ?? 0),
      ];
    case 'sections':
      return [
        { header: 'Section', className: 'nowrap', cell: (e) => <span className="cell-title">{academicLabel(e.record as AcademicRecord, snapshot)}</span> },
        text('Program', (r) => acronym((r as Of<'sections'>).program_id)),
        count('Year', (r) => (r as Of<'sections'>).year_level ?? '—'),
        count('Population', (r) => (r as Of<'sections'>).population ?? '—'),
      ];
    case 'faculty':
      return [
        { header: 'Name', cell: (e) => <span className="cell-title">{(e.record as Of<'faculty'>).name}</span> },
        count('Eligible subjects', (r) => (r as Of<'faculty'>).subject_ids?.length ?? 0),
        count('Availability windows', (r) => (r as Of<'faculty'>).availability?.length ?? 0),
      ];
    case 'offerings':
      return [
        {
          header: 'Subject',
          cell: (e) => {
            const record = e.record as Of<'offerings'>;
            const subject = subjects.find((s) => s.id === record.subject_id);
            return title(subject?.code ?? 'Unknown subject', subject?.name);
          },
        },
        text(
          'Section',
          (r) => {
            const section = sections.find((s) => s.id === (r as Of<'offerings'>).section_id);
            return section ? academicLabel(section, snapshot) : 'Unknown section';
          },
          true,
        ),
        count('Faculty', (r) => (r as Of<'offerings'>).teacher_ids?.length ?? 0),
        count('Classrooms', (r) => (r as Of<'offerings'>).room_ids?.length ?? 0),
      ];
    case 'resources':
      return [
        {
          header: 'Room',
          cell: (e) => {
            const room = e.record as Of<'resources'>;
            return title(room.name, room.building);
          },
        },
        text('Scheduling', (r) => {
          const room = r as Of<'resources'>;
          return room.condition === 'operational' && room.schedulable
            ? 'Operational metadata entered'
            : 'Not verified for scheduling';
        }),
        count('Capacity', (r) => {
          const room = r as Of<'resources'>;
          return room.capacity_verified ? `${room.capacity} verified capacity` : 'Capacity unverified';
        }),
      ];
    case 'constraints':
      return [
        { header: 'Rule set', cell: (e) => <span className="cell-title">{academicLabel(e.record as AcademicRecord, snapshot)}</span> },
        count('Operating windows', (r) => (r as Of<'constraints'>).operating_windows?.length ?? 0),
      ];
    default:
      return [];
  }
}

/** One hairline table for every academic record category. */
export function AcademicRecordTable({
  kind,
  label,
  snapshot,
  entries,
  busy,
  onEdit,
  onDelete,
}: {
  kind: AcademicKind;
  label: string;
  snapshot: AcademicSnapshot;
  entries: Entry[];
  busy: boolean;
  onEdit: (id: string) => void;
  onDelete: (entry: Entry) => void;
}) {
  return (
    <DataTable
      label={label}
      rows={entries}
      rowKey={(entry) => entry.record.id!}
      columns={[
        ...columnsFor(kind, snapshot),
        {
          header: 'Status',
          className: 'nowrap',
          cell: (entry) => {
            const inactive = 'active' in entry.record && entry.record.active === false;
            return (
              <StatusBadge tone={inactive ? 'warning' : 'neutral'}>
                {inactive ? 'Inactive' : 'Saved'}
              </StatusBadge>
            );
          },
        },
        {
          header: 'Actions',
          unlabelled: true,
          cell: (entry) => {
            const name = academicLabel(entry.record as AcademicRecord, snapshot);
            return (
              <div className="row-actions">
                <Button variant="secondary" aria-label={`Edit ${name}`} onClick={() => onEdit(entry.record.id!)}>
                  Edit
                </Button>
                <Button variant="ghost" disabled={busy} aria-label={`Delete ${name}`} onClick={() => onDelete(entry)}>
                  Delete
                </Button>
              </div>
            );
          },
        },
      ]}
    />
  );
}
