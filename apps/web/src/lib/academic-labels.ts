import type { AcademicKind, AcademicRecord, AcademicSnapshot } from './academic-api';
export const academicTabs: Array<{ kind: AcademicKind; label: string; path: string }> = [
  { kind: 'programs', label: 'Programs', path: '/admin/programs' },
  { kind: 'subjects', label: 'Subjects', path: '/admin/subjects' },
  { kind: 'sections', label: 'Sections', path: '/admin/sections' },
  { kind: 'faculty', label: 'Faculty', path: '/admin/teachers' },
  { kind: 'offerings', label: 'Subject Offerings', path: '/admin/offerings' },
  { kind: 'resources', label: 'Resource Metadata', path: '/admin/academic/resources' },
  { kind: 'constraints', label: 'Scheduling Constraints', path: '/admin/scheduling-constraints' },
];
export const academicPath = (kind: AcademicKind, period = '') => `${academicTabs.find(t => t.kind === kind)!.path}${period ? `?period=${encodeURIComponent(period)}` : ''}`;
export const academicRecords = (snapshot: AcademicSnapshot, kind?: AcademicKind) => snapshot.records.filter(e => !kind || e.record.kind === kind).map(e => e.record as AcademicRecord);
export function academicLabel(record: AcademicRecord, snapshot: AcademicSnapshot): string {
  if (record.kind === 'programs') return `${record.acronym} · ${record.name}`;
  if (record.kind === 'subjects') return `${record.code} · ${record.name}`;
  if (record.kind === 'sections') {
    const program = academicRecords(snapshot, 'programs').find(p => p.id === record.program_id);
    return record.custom_label || `${program?.kind === 'programs' ? program.acronym : record.program_id}-${record.year_level}${record.section_letter}`;
  }
  if (record.kind === 'offerings') {
    const subject = academicRecords(snapshot, 'subjects').find(s => s.id === record.subject_id);
    const section = academicRecords(snapshot, 'sections').find(s => s.id === record.section_id);
    return `${subject?.kind === 'subjects' ? subject.code : record.subject_id} · ${section ? academicLabel(section, snapshot) : record.section_id}`;
  }
  if (record.kind === 'constraints') return 'Weekly operating rules';
  if (record.kind === 'resources') return `${record.name}${record.alias ? ` · ${record.alias}${record.alias_unconfirmed ? ' (unconfirmed)' : ''}` : ''} · ${record.building}`;
  return record.name;
}
