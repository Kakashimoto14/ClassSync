import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AcademicManagementPage } from './AcademicManagementPage';
import * as api from '../lib/academic-api';
import type { AcademicSnapshot } from '../lib/academic-api';

vi.mock('../lib/academic-api', () => ({
  loadCurriculumCatalog: vi.fn(),
  listAcademicPeriods: vi.fn(),
  createAcademicPeriod: vi.fn(),
  loadAcademicPeriod: vi.fn(),
  saveAcademicRecord: vi.fn(),
  checkAcademicReadiness: vi.fn(),
  generateAcademicSchedule: vi.fn(),
}));
vi.mock('../lib/scheduling-api', () => ({ schedulingSandboxEnabled: true }));

const period = {
  id: 'period-a', title: 'Shared campus term', revision: 2,
  created_at: '2026-10-18T00:00:00+00:00', source: 'development-entered' as const,
};
const entry = (record: Record<string, unknown>) => ({
  revision: 1, updated_at: period.created_at, updated_by: 'admin', record,
});
const snapshot = {
  period,
  records: [
    entry({ kind: 'programs', id: 'bsit', acronym: 'BSIT', name: 'Information Technology',
      institute: 'Institute of Computer Studies', section_policy: 'degree', active: true }),
    entry({ kind: 'programs', id: 'bse', acronym: 'BSE', name: 'Entrepreneurship',
      institute: 'Institute of Business', section_policy: 'degree', active: true }),
    entry({ kind: 'subjects', id: 'it-sub', code: 'IT101', name: 'Computing Fundamentals',
      required_weekly_minutes: 180, patterns: [{ id: 'one', durations: [180] }],
      program_ids: ['bsit'] }),
    entry({ kind: 'subjects', id: 'bse-sub', code: 'ENT101', name: 'Opportunity Seeking',
      required_weekly_minutes: 180, patterns: [{ id: 'one', durations: [180] }],
      program_ids: ['bse'] }),
  ],
} as unknown as AcademicSnapshot;

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.loadCurriculumCatalog).mockResolvedValue({
    status: 'unreviewed', versions: [], courses: [], program_ids: {},
  } as never);
  vi.mocked(api.listAcademicPeriods).mockResolvedValue({ periods: [period] });
  vi.mocked(api.loadAcademicPeriod).mockResolvedValue(snapshot);
  vi.mocked(api.checkAcademicReadiness).mockResolvedValue(null as never);
  HTMLElement.prototype.scrollIntoView = vi.fn();
});

describe('Institute and Program filters on setup tabs', () => {
  it('narrows subjects by institute and program with labelled controls', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/subjects?period=period-a']}>
        <AcademicManagementPage initialKind="subjects" />
      </MemoryRouter>,
    );
    await screen.findByText(/Computing Fundamentals/);
    expect(screen.getByText(/Computing Fundamentals/)).toBeInTheDocument();
    expect(screen.getByText(/Opportunity Seeking/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Institute'), { target: { value: 'IBE' } });
    expect(screen.queryByText(/Computing Fundamentals/)).not.toBeInTheDocument();
    expect(screen.getByText(/Opportunity Seeking/)).toBeInTheDocument();
    // Program choices follow the selected institute.
    const program = screen.getByLabelText('Program');
    expect([...(program as HTMLSelectElement).options].map((o) => o.text)).toEqual([
      'All programs', 'BSE',
    ]);

    fireEvent.change(screen.getByLabelText('Institute'), { target: { value: 'all' } });
    fireEvent.change(screen.getByLabelText('Program'), { target: { value: 'bsit' } });
    expect(screen.getByText(/Computing Fundamentals/)).toBeInTheDocument();
    expect(screen.queryByText(/Opportunity Seeking/)).not.toBeInTheDocument();
  });
});
