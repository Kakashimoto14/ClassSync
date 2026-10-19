import { render, screen } from '@testing-library/react';
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
    await screen.findByRole('link', { name: 'Generate Weekly Schedule' }),
  ).toHaveAttribute('href', '/admin/ai-scheduling?period=p');
  expect(screen.getByText('No published version for this period')).toBeInTheDocument();
});
it('leads blocked periods to requirements rather than a generation promise', async () => {
  vi.mocked(academic.checkAcademicReadiness).mockResolvedValue({
    ...readiness,
    ready: false,
    issues: [{ severity: 'blocking', code: 'no_eligible_room', message: 'No suitable classroom' }],
  });
  render(
    <MemoryRouter>
      <AdminSchedulingHome />
    </MemoryRouter>,
  );
  expect(
    await screen.findByRole('link', { name: 'Review Requirements' }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole('link', { name: 'Generate Weekly Schedule' }),
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
    screen.queryByRole('link', { name: 'Generate Weekly Schedule' }),
  ).not.toBeInTheDocument();
});
