import { describe, expect, it } from 'vitest';
import { instituteCode, programScope } from './program-scope';

const records = [
  { kind: 'programs', id: 'bsit', acronym: 'BSIT', institute: 'Institute of Computer Studies' },
  { kind: 'programs', id: 'bse', acronym: 'BSE', institute: 'Institute of Business' },
  { kind: 'programs', id: 'beed-gen', acronym: 'BEEd-GEN', institute: 'Institute of Education' },
  { kind: 'subjects', id: 'it-sub', program_ids: ['bsit'] },
  { kind: 'subjects', id: 'ge-sub', program_ids: ['bse', 'beed-gen'] },
  { kind: 'sections', id: 'it-1a', program_id: 'bsit' },
  { kind: 'sections', id: 'bse-1a', program_id: 'bse' },
  { kind: 'offerings', id: 'o-it', section_id: 'it-1a' },
  { kind: 'offerings', id: 'o-bse', section_id: 'bse-1a' },
  { kind: 'faculty', id: 'shared', subject_ids: ['ge-sub'] },
  { kind: 'faculty', id: 'it-only', subject_ids: ['it-sub'] },
];

describe('Institute and Program scope', () => {
  it('maps catalog institute names to ICS, IBE and ITE', () => {
    expect(instituteCode('Institute of Computer Studies (ICS)')).toBe('ICS');
    expect(instituteCode('Institute of Business')).toBe('IBE');
    expect(instituteCode('Institute of Education (ITE)')).toBe('ITE');
    expect(instituteCode('Unknown')).toBeNull();
  });

  it('derives programs for offerings via sections and for faculty via subjects', () => {
    const scope = programScope(records);
    const find = (id: string) => records.find((r) => r.id === id)!;
    expect(scope.programsOf(find('o-bse'))).toEqual(['bse']);
    expect(scope.programsOf(find('shared')).sort()).toEqual(['beed-gen', 'bse']);
    expect(scope.matches(find('shared'), 'ITE', 'all')).toBe(true);
    expect(scope.matches(find('shared'), 'ICS', 'all')).toBe(false);
    expect(scope.matches(find('it-only'), 'all', 'bsit')).toBe(true);
    expect(scope.matches(find('o-it'), 'IBE', 'all')).toBe(false);
    expect(scope.matches(find('o-it'), 'all', 'all')).toBe(true);
    expect(scope.programs.map((p) => p.acronym)).toEqual(['BEEd-GEN', 'BSE', 'BSIT']);
  });
});
