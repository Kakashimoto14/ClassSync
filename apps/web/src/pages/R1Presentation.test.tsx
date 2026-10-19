import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { RoleScheduleWorkspace } from './RoleScheduleWorkspace';
import { PresentationConflictSummary } from '../components/scheduling/PresentationConflictSummary';
import { PublishedRoomAvailability } from './PublishedRoomAvailability';
import { readWorkspace, rememberWorkspace } from '../lib/workspace-context';
import { subscribeTimetable, timetableRequest } from '../lib/publication-api';
vi.mock('../lib/presentation-sample', async (original) => ({
  ...(await original<typeof import('../lib/presentation-sample')>()),
  presentationOnlyBuild: true,
}));
vi.mock('../lib/publication-api', () => ({
  timetableRequest: vi.fn(),
  subscribeTimetable: vi.fn(),
}));
beforeEach(() => {
  sessionStorage.clear();
  vi.clearAllMocks();
});
afterEach(() => {
  sessionStorage.clear();
  vi.unstubAllGlobals();
});
function saved(mode: 'published' | 'presentation', identity: string) {
  rememberWorkspace('student', {
    mode,
    identity,
    period: 'old-private-period',
    draft: 'private-draft',
    date: '2026-10-20',
    view: 'day',
  });
}
it('uses only the reviewed bundled source for stale sessions and hostile connected-source query parameters', async () => {
  saved('published', 'old-enrollment');
  const fetcher = vi.fn();
  vi.stubGlobal('fetch', fetcher);
  render(
    <MemoryRouter
      initialEntries={['/student/schedule?review=private&mode=published&period=private']}
    >
      <RoleScheduleWorkspace role="student" />
    </MemoryRouter>,
  );
  await waitFor(() =>
    expect(document.querySelectorAll('.ux-agenda-row').length).toBeGreaterThan(0),
  );
  await waitFor(() =>
    expect(readWorkspace('student')).toMatchObject({
      mode: 'presentation',
      period: 'classsync-presentation-v1',
      draft: '',
      identity: 'syn-bsit-3-A',
    }),
  );
  expect(timetableRequest).not.toHaveBeenCalled();
  expect(subscribeTimetable).not.toHaveBeenCalled();
  expect(fetcher).not.toHaveBeenCalled();
});
it('recovers an invalid presentation identity deliberately without substituting private data', async () => {
  saved('presentation', 'missing-identity');
  render(
    <MemoryRouter>
      <RoleScheduleWorkspace role="student" />
    </MemoryRouter>,
  );
  expect(await screen.findByRole('alert')).toHaveTextContent('Choose an identity included');
  fireEvent.click(screen.getByRole('button', { name: 'Reset sample identity' }));
  await waitFor(() =>
    expect(document.querySelectorAll('.ux-agenda-row').length).toBeGreaterThan(0),
  );
  expect(timetableRequest).not.toHaveBeenCalled();
});
it('keeps the loaded agenda when selecting another date within the same sample month', async () => {
  saved('published', 'old-enrollment');
  render(
    <MemoryRouter>
      <RoleScheduleWorkspace role="student" />
    </MemoryRouter>,
  );
  await waitFor(() =>
    expect(document.querySelectorAll('.ux-agenda-row').length).toBeGreaterThan(0),
  );
  fireEvent.click(
    within(screen.getByRole('group', { name: 'Selected week' })).getByRole('button', {
      name: /Thu, Oct 22/,
    }),
  );
  await waitFor(() => expect(readWorkspace('student').date).toBe('2026-10-22'));
  expect(document.querySelectorAll('.ux-agenda-row').length).toBeGreaterThan(0);
  expect(timetableRequest).not.toHaveBeenCalled();
});
it('reports only stored conflict validation at export without providing a live validator', async () => {
  render(<PresentationConflictSummary />);
  expect(await screen.findByText('0 hard conflicts at export')).toBeInTheDocument();
  expect(screen.getByText(/No new validation or live conflict analysis/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Validate timetable' })).not.toBeInTheDocument();
  expect(timetableRequest).not.toHaveBeenCalled();
});
it('does not offer live occupancy even before a returning role context is persisted', () => {
  saved('published', 'old');
  render(<PublishedRoomAvailability role="student" rooms={[{ id: 'room', name: 'Room' }]} />);
  expect(screen.getByText(/Live room occupancy is unavailable/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Check occupancy' })).not.toBeInTheDocument();
});
