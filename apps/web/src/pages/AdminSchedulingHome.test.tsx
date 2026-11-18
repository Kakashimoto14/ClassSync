import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import * as academic from '../lib/academic-api';
import * as scheduling from '../lib/scheduling-api';
import { timetableRequest } from '../lib/publication-api';
import { AdminSchedulingHome } from './AdminSchedulingHome';
vi.mock('../lib/academic-api', () => ({
  listAcademicPeriods: vi.fn(),
  checkAcademicReadiness: vi.fn(),
}));
vi.mock('../lib/scheduling-api', () => ({
  schedulingSandboxEnabled: true,
  listSchedulingDrafts: vi.fn(),
}));
vi.mock('../lib/publication-api', () => ({ timetableRequest: vi.fn() }));
const period = {
  id: 'p',
  title: 'Sample period',
  revision: 2,
  source: 'development-entered' as const,
  created_at: '2026-10-19T00:00:00Z',
};
const readiness = {
  period,
  ready: true,
  issues: [],
  programs: 1,
  subjects: 2,
  sections: 1,
  faculty: 2,
  offerings: 2,
  eligible_resources: 4,
  inputs: null,
};
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  vi.mocked(academic.listAcademicPeriods).mockResolvedValue({ periods: [period] });
  vi.mocked(academic.checkAcademicReadiness).mockResolvedValue(readiness);
  vi.mocked(scheduling.listSchedulingDrafts).mockResolvedValue({
    drafts: [],
    has_more: false,
    limit: 25,
    offset: 0,
  });
  vi.mocked(timetableRequest).mockResolvedValue({ periods: [] });
});
it('uses real readiness to lead with generation without claiming publication', async () => {
  render(
    <MemoryRouter>
      <AdminSchedulingHome />
    </MemoryRouter>,
  );
  expect(
    await screen.findByRole('link', { name: 'Generate weekly schedule' }),
  ).toHaveAttribute('href', '/admin/ai-scheduling?period=p');
  expect(screen.getByText('No published timetable is recorded for this period.')).toBeInTheDocument();
  expect(timetableRequest).toHaveBeenCalledWith('sandbox/periods');
});
it('leads blocked periods to requirements rather than a generation promise', async () => {
  vi.mocked(academic.checkAcademicReadiness).mockResolvedValue({
    ...readiness,
    ready: false,
    issues: [
      { severity: 'blocking', code: 'missing_offerings', message: 'Create offerings.' },
      { severity: 'blocking', code: 'missing_operating_hours', message: 'Set permitted hours.' },
      { severity: 'blocking', code: 'section_without_offerings', message: 'Section needs offerings.' },
      { severity: 'blocking', code: 'no_eligible_room', message: 'No suitable classroom' },
    ],
  });
  render(
    <MemoryRouter>
      <AdminSchedulingHome />
    </MemoryRouter>,
  );
  expect(await screen.findByRole('link', { name: 'Set up offerings' })).toHaveAttribute(
    'href',
    '/admin/offerings?period=p',
  );
  expect(screen.getByRole('link', { name: 'Set operating hours' })).toHaveAttribute(
    'href',
    '/admin/scheduling-constraints?period=p',
  );
  expect(screen.getByText('Section needs offerings.')).toBeInTheDocument();
  expect(screen.getByText('Show 1 more blockers')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Resolve next blocker' })).toHaveAttribute(
    'href',
    '/admin/offerings?period=p',
  );
  expect(screen.getAllByRole('link', { name: /offerings/i })).toHaveLength(3);
  expect(screen.queryByRole('link', { name: 'Review requirement' })).not.toBeInTheDocument();
  expect(
    screen.queryByRole('link', { name: 'Generate weekly schedule' }),
  ).not.toBeInTheDocument();
});
it('keeps failed backend status recoverable without a fake ready state', async () => {
  vi.mocked(academic.listAcademicPeriods).mockRejectedValue(new Error('Gateway unavailable'));
  render(
    <MemoryRouter>
      <AdminSchedulingHome />
    </MemoryRouter>,
  );
  expect(await screen.findByRole('alert')).toHaveTextContent('Gateway unavailable');
  expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  expect(
    screen.queryByRole('link', { name: 'Generate weekly schedule' }),
  ).not.toBeInTheDocument();
});

it('shows period-scoped KPI cards and the publication/draft panels from connected results', async () => {
  render(
    <MemoryRouter>
      <AdminSchedulingHome />
    </MemoryRouter>,
  );
  expect(await screen.findByRole('link', { name: /Active sections 1/ })).toHaveAttribute(
    'href',
    '/admin/sections?period=p',
  );
  expect(screen.getByRole('link', { name: /Subject offerings 2/ })).toHaveAttribute(
    'href',
    '/admin/offerings?period=p',
  );
  expect(screen.getByRole('link', { name: /Schedulable spaces 4/ })).toHaveAttribute(
    'href',
    '/admin/academic/resources?period=p',
  );
  expect(screen.getByRole('link', { name: /Saved drafts 0/ })).toHaveAttribute(
    'href',
    '/admin/schedule-manager/drafts?source=academic',
  );
  expect(screen.getByRole('heading', { name: 'Published timetable' })).toBeInTheDocument();
  expect(screen.getByText('No published timetable is recorded for this period.')).toBeInTheDocument();
  expect(screen.getByText(/No saved draft is recorded/)).toBeInTheDocument();
  expect(screen.queryByRole('navigation', { name: 'Scheduling tools' })).not.toBeInTheDocument();
});

it('refreshes connected dashboard records without exposing stale data as a new period', async () => {
  const nextPeriod = { ...period, id: 'p-2', title: 'Next term' };
  vi.mocked(academic.listAcademicPeriods).mockResolvedValue({ periods: [period, nextPeriod] });
  let resolveNext: ((value: typeof readiness) => void) | undefined;
  vi.mocked(academic.checkAcademicReadiness)
    .mockResolvedValueOnce(readiness)
    .mockImplementationOnce(() => new Promise((resolve) => { resolveNext = resolve; }));
  render(
    <MemoryRouter>
      <AdminSchedulingHome />
    </MemoryRouter>,
  );
  expect(await screen.findByRole('link', { name: /Active sections 1/ })).toBeInTheDocument();
  fireEvent.change(screen.getByRole('combobox', { name: 'Academic period' }), {
    target: { value: 'p-2' },
  });
  expect(await screen.findByRole('status')).toHaveTextContent('Checking academic readiness');
  expect(screen.queryByRole('link', { name: /Active sections/ })).not.toBeInTheDocument();
  resolveNext?.({ ...readiness, period: nextPeriod, sections: 7 });
  await waitFor(() => expect(screen.getByRole('link', { name: /Active sections 7/ })).toBeInTheDocument());
  expect(vi.mocked(academic.checkAcademicReadiness)).toHaveBeenCalledTimes(2);
});

it('does not label publication as unpublished when its status request fails', async () => {
  vi.mocked(timetableRequest).mockRejectedValue(new Error('Publication service unavailable'));
  render(
    <MemoryRouter>
      <AdminSchedulingHome />
    </MemoryRouter>,
  );
  expect(await screen.findByText('Publication status is unavailable.')).toBeInTheDocument();
  expect(screen.getByText('Unavailable')).toBeInTheDocument();
  expect(screen.queryByText('Unpublished')).not.toBeInTheDocument();
});
