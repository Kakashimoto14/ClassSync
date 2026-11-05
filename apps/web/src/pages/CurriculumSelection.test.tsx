import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { beforeEach, expect, it, vi } from 'vitest';
import { CurriculumSelection } from './CurriculumSelection';
import { loadCurriculumCatalog, type AcademicRecord } from '../lib/academic-api';

vi.mock('../lib/academic-api', () => ({ loadCurriculumCatalog: vi.fn() }));
const fixture = {
  status: 'unreviewed',
  program_ids: { BSIT: 'bsit' },
  versions: [
    {
      id: 'v24',
      institute: 'ICS',
      program: 'BSIT',
      entry_cohort: '2024',
      source_pdf: '24_BSIT.pdf',
      printed_curriculum_ay: '2023-2024',
      source_sha256: 'hash24',
      source_archive_member: '24/ICS/24_BSIT.pdf',
    },
    {
      id: 'v26',
      institute: 'ICS',
      program: 'BSIT',
      entry_cohort: '2026',
      source_pdf: '26_BSIT.pdf',
      printed_curriculum_ay: '2026-2027',
      source_sha256: 'hash26',
      source_archive_member: '26/ICS/26_BSIT.pdf',
    },
  ],
  courses: [
    {
      id: 'c24',
      curriculum_version_id: 'v24',
      subject_code: 'ITIASE1',
      subject_title: 'Information Assurance and Security 1',
      year_level: '3',
      semester: '1',
      program: 'BSIT',
      lec_hours_printed: '2',
      lab_hours_printed: '1',
      units_printed: '3',
      prerequisite_printed: '',
      pdf_page: '2',
    },
  ],
};
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(loadCurriculumCatalog).mockResolvedValue(fixture);
});
function Harness({ section = false }) {
  const [record, setRecord] = useState<AcademicRecord>(
    section
      ? {
          id: 'sec',
          kind: 'sections',
          period_id: 'p',
          program_id: 'bsit',
          year_level: 3,
          section_letter: 'A',
        }
      : { id: 'sub', kind: 'subjects', code: '', name: '' },
  );
  return (
    <>
      <CurriculumSelection record={record} onChange={setRecord} />
      <output aria-label="Selected record">{JSON.stringify(record)}</output>
    </>
  );
}
it('selects exact source code and leaves minutes unapproved despite printed hours', async () => {
  render(<Harness />);
  await screen.findByRole('combobox', { name: 'Curriculum source' });
  fireEvent.change(screen.getByRole('combobox', { name: 'Curriculum source' }), {
    target: { value: 'v24' },
  });
  fireEvent.change(screen.getByRole('combobox', { name: 'Exact curriculum course' }), {
    target: { value: 'c24' },
  });
  const selected = JSON.parse(screen.getByLabelText('Selected record').textContent!);
  expect(selected).toMatchObject({
    code: 'ITIASE1',
    curriculum_version_id: 'v24',
    curriculum_course_id: 'c24',
    required_weekly_minutes: null,
    patterns: [],
    contact_minutes_verified: false,
  });
  expect(screen.getByText(/Printed hours are evidence only/)).toBeVisible();
});
it('stores explicit entry cohort separately from current year', async () => {
  render(<Harness section />);
  await screen.findByRole('combobox', { name: 'Curriculum source' });
  fireEvent.change(screen.getByRole('combobox', { name: 'Curriculum source' }), {
    target: { value: 'v24' },
  });
  expect(JSON.parse(screen.getByLabelText('Selected record').textContent!)).toMatchObject({
    year_level: 3,
    entry_cohort_year: 2024,
    curriculum_version_id: 'v24',
  });
});
it('shows an observable unavailable state and retries without sample fallback', async () => {
  vi.mocked(loadCurriculumCatalog).mockRejectedValueOnce(new Error('Catalog unavailable'));
  render(<Harness />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Catalog unavailable');
  fireEvent.click(screen.getByRole('button', { name: 'Retry curriculum catalog' }));
  await waitFor(() =>
    expect(screen.getByRole('combobox', { name: 'Curriculum source' })).toBeVisible(),
  );
  expect(loadCurriculumCatalog).toHaveBeenCalledTimes(2);
});
