import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { AcademicStudentRosterPage } from './AcademicStudentRosterPage';

// Only the transport is faked, so the real period list and default selection run.
const fixture = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('../lib/institutional-api', () => ({ institutionalRequest: fixture.request }));
vi.mock('../config/runtime-config', () => ({
  appMode: 'institutional',
  requireLiveCapability: vi.fn(),
}));

const period = (id: string, title: string, revision: number) => ({
  id,
  title,
  revision,
  created_at: '2026-11-01T00:00:00Z',
  source: 'institutional',
});

beforeEach(() => {
  vi.clearAllMocks();
  fixture.request.mockImplementation(async (path: string) =>
    path === 'academic/periods'
      ? {
          periods: [
            // Listed first and with the higher revision, as observed in production.
            period(
              'defense-ay-2026-2027-first',
              'Archived invalid period · defense-ay-2026-2027-first',
              214,
            ),
            period('valid-period', 'AY 2026-2027 · 1st Semester', 213),
          ],
        }
      : { items: [], total: 0, limit: 20, offset: 0, period_revision: 213, sections: [] },
  );
});

it('never offers or auto-selects an archived period, even with a higher revision', async () => {
  render(
    <MemoryRouter>
      <AcademicStudentRosterPage />
    </MemoryRouter>,
  );
  const selector = screen.getByLabelText('Academic period');
  await waitFor(() => expect(selector).toHaveValue('valid-period'));
  expect(screen.queryByRole('option', { name: /Archived invalid period/ })).not.toBeInTheDocument();
  await waitFor(() =>
    expect(fixture.request).toHaveBeenCalledWith(
      expect.stringContaining('academic/periods/valid-period/roster'),
      expect.anything(),
    ),
  );
  expect(
    fixture.request.mock.calls.filter(([path]) =>
      String(path).includes('defense-ay-2026-2027-first'),
    ),
  ).toHaveLength(0);
});
