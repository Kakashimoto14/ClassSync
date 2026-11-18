import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import type { DraftDetail } from '../lib/scheduling-api';
const source = vi.hoisted(() => ({ request: vi.fn(), timetable: vi.fn(), academic: vi.fn() }));
vi.mock('../config/runtime-config', () => ({ appMode: 'institutional' }));
vi.mock('../lib/institutional-api', () => ({ institutionalRequest: source.request }));
vi.mock('../lib/publication-api', () => ({ timetableRequest: source.timetable }));
vi.mock('../lib/academic-api', () => ({ loadAcademicPeriod: source.academic }));
vi.mock('./OccurrenceExceptionEditor', () => ({ OccurrenceExceptionEditor: () => null }));
import { PublicationPanel } from './PublicationPanel';
const draft = {
  id: 'owned-draft',
  period_id: 'owned-period',
  input_snapshot: { synthetic: false },
} as unknown as DraftDetail;
const calendar = { effective_start: '2026-10-01', effective_end: '2026-12-31', exceptions: [] };
beforeEach(() => {
  vi.clearAllMocks();
  source.academic.mockResolvedValue({ period: { revision: 2, calendar } });
  source.timetable.mockImplementation(async (path) =>
    path.startsWith('history/')
      ? { versions: [{ id: 'owned-publication', draft_id: 'owned-draft', calendar, revision: 2 }] }
      : { sections: 1, teachers: 1, rooms: 1, occurrences: 1 },
  );
  source.request.mockImplementation(async (path) => {
    if (path.endsWith('/invalid')) throw new Error('This request is unavailable');
    return {
      id: 'approved',
      publication_id: 'owned-publication',
      draft_id: 'owned-draft',
      status: 'approved',
      revision: 2,
      context: {
        original_date: '2026-11-09',
        class: {
          assignment_id: 'owned-session',
          subject: { code: 'TEST101' },
          date: '2026-11-09',
          starts_at: '2026-11-09T08:00:00+08:00',
          room: { name: 'Original' },
        },
        proposed_room: { id: 'approved-room', name: 'Approved alternative' },
      },
    };
  });
});
function Harness() {
  const navigate = useNavigate();
  return (
    <>
      <button onClick={() => navigate('?request=invalid')}>Open another request</button>
      <PublicationPanel draft={draft} source="academic" />
    </>
  );
}
it('discards a ready calendar when the request scope changes to an invalid request', async () => {
  render(
    <MemoryRouter initialEntries={['/draft?request=approved']}>
      <Harness />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByText('Review publication', { exact: true }));
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Revalidate for publication' })).toBeEnabled(),
  );
  fireEvent.click(screen.getByRole('button', { name: 'Revalidate for publication' }));
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Publish reviewed timetable' })).toBeEnabled(),
  );
  fireEvent.click(screen.getByRole('button', { name: 'Open another request' }));
  await screen.findByRole('alert');
  expect(screen.getByRole('button', { name: 'Publish reviewed timetable' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Revalidate for publication' })).toBeDisabled();
  expect(screen.queryByText(/Approved request: TEST101/)).not.toBeInTheDocument();
  expect(source.timetable.mock.calls.some(([path]) => path === 'publish')).toBe(false);
});
