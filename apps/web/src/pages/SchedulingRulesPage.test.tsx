import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { SchedulingRulesPage } from './SchedulingRulesPage';
import { PolishSummary } from './PolishSummary';

const api = vi.hoisted(() => ({ list: vi.fn(), load: vi.fn(), save: vi.fn() }));
vi.mock('../lib/academic-api', () => ({
  listAcademicPeriods: api.list,
  loadAcademicPeriod: api.load,
  saveAcademicRecord: api.save,
}));

const period = { id: 'p1', title: 'Term one', revision: 3, source: 'institutional' };
const rules = {
  id: 'rules',
  kind: 'constraints',
  transition_buffer_minutes: 10,
  operating_windows: [{ day: 0, start: 420, end: 1260 }],
};
const snapshot = { period, records: [{ record: rules, revision: 2 }] };

beforeEach(() => {
  vi.clearAllMocks();
  api.list.mockResolvedValue({ periods: [period] });
  api.load.mockResolvedValue(snapshot);
  api.save.mockResolvedValue(snapshot);
});
const open = () =>
  render(
    <MemoryRouter initialEntries={['/admin/institutional-rules?period=p1']}>
      <SchedulingRulesPage />
    </MemoryRouter>,
  );

it('saves day-shape rules and the pattern default without touching other constraints', async () => {
  open();
  fireEvent.click(await screen.findByRole('button', { name: 'Fill commuter defaults' }));
  const longest = screen.getByLabelText('Longest day, first class to last (hours)');
  expect(longest).toHaveValue(9);
  fireEvent.change(longest, { target: { value: '10' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save rules' }));
  await waitFor(() => expect(api.save).toHaveBeenCalledOnce());
  expect(api.save).toHaveBeenCalledWith('p1', {
    expected_revision: 2,
    record: {
      ...rules,
      daily_shape: {
        min_sessions_per_active_day: 2,
        max_sessions_per_day: 4,
        max_daily_span_minutes: 600,
      },
      pattern_policy_180: 'flexible',
    },
  });
  expect(await screen.findByRole('status')).toHaveTextContent('Rules saved');
});

it('keeps the entered values and offers a reload when a save is rejected', async () => {
  api.save.mockRejectedValue(new Error('This record changed. Reload before saving.'));
  open();
  fireEvent.change(await screen.findByLabelText('Most classes on a class day'), {
    target: { value: '3' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Save rules' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Reload before saving');
  expect(screen.getByLabelText('Most classes on a class day')).toHaveValue(3);
  fireEvent.click(screen.getByRole('button', { name: 'Reload saved rules' }));
  await waitFor(() => expect(api.load).toHaveBeenCalledTimes(2));
});

it('reports the before and after measures and each section-day still outside them', () => {
  const metrics = {
    orphan_section_days: 6,
    short_section_days: 6,
    over_span_section_days: 5,
    over_max_section_days: 0,
    max_span_minutes: 840,
    lectures_in_specialized_rooms: 0,
    faculty_clopenings: 2,
    idle_gap_minutes: 600,
  };
  render(
    <PolishSummary
      input={{
        period_id: 'p1',
        data_version: 'v',
        scope_description: 's',
        programs: [{ id: 'bsit', acronym: 'BSIT', name: 'IT', institute: 'ICS' }],
        sections: [{ id: 's1', program_id: 'bsit', year_level: 3, section_letter: 'A' }],
      }}
      report={{
        moves: 4,
        evaluations: 100,
        elapsed_ms: 12,
        truncated: false,
        before: metrics,
        after: { ...metrics, orphan_section_days: 0, max_span_minutes: 630 },
        unmet: [
          { section_id: 's1', day: 4, sessions: 3, span_minutes: 630, issues: ['over_span'] },
        ],
      }}
    />,
  );
  const row = screen.getByRole('row', { name: /One-class section-days/ });
  expect(within(row).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['6', '0']);
  expect(screen.getByText(/BSIT-3A · Friday: 3 classes over 10.5 h/)).toHaveTextContent(
    'day too long',
  );
});
