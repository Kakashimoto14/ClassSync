// Institute/Program scope for setup lists and timetables, derived from existing references:
// sections name a program, subjects list programs, offerings inherit their section's program
// and faculty inherit the programs of the subjects they are eligible to teach.

export type InstituteCode = 'ICS' | 'IBE' | 'ITE';
export const INSTITUTES: InstituteCode[] = ['ICS', 'IBE', 'ITE'];

export type ScopedRecord = {
  kind: string;
  id: string;
  program_id?: string;
  program_ids?: string[];
  section_id?: string;
  subject_ids?: string[];
  institute?: string;
  acronym?: string;
};

export function instituteCode(institute: string | undefined): InstituteCode | null {
  const value = (institute ?? '').toLowerCase();
  if (value.includes('computer studies') || /\bics\b/.test(value)) return 'ICS';
  if (value.includes('business') || /\bibe\b/.test(value)) return 'IBE';
  if (value.includes('education') || /\bite\b/.test(value)) return 'ITE';
  return null;
}

export function programScope(records: ScopedRecord[]) {
  const byKind = (kind: string) => records.filter((record) => record.kind === kind);
  const sectionProgram = new Map(byKind('sections').map((s) => [s.id, s.program_id ?? '']));
  const subjectPrograms = new Map(byKind('subjects').map((s) => [s.id, s.program_ids ?? []]));
  const programs = byKind('programs');
  const institute = new Map(programs.map((p) => [p.id, instituteCode(p.institute)]));

  function programsOf(record: ScopedRecord): string[] {
    switch (record.kind) {
      case 'programs': return [record.id];
      case 'subjects': return record.program_ids ?? [];
      case 'sections': return record.program_id ? [record.program_id] : [];
      case 'offerings': return [sectionProgram.get(record.section_id ?? '') ?? ''].filter(Boolean);
      case 'faculty':
        return [...new Set((record.subject_ids ?? []).flatMap((id) => subjectPrograms.get(id) ?? []))];
      default: return [];
    }
  }

  function matches(record: ScopedRecord, instituteFilter: string, programFilter: string) {
    if (instituteFilter === 'all' && programFilter === 'all') return true;
    const owned = programsOf(record);
    if (programFilter !== 'all' && !owned.includes(programFilter)) return false;
    return instituteFilter === 'all' || owned.some((id) => institute.get(id) === instituteFilter);
  }

  return {
    programs: programs
      .map((p) => ({ id: p.id, acronym: p.acronym ?? p.id, institute: institute.get(p.id) }))
      .sort((a, b) => a.acronym.localeCompare(b.acronym)),
    programsOf,
    matches,
  };
}
