import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
const fixture = vi.hoisted(() => ({ request: vi.fn(), restrictions: vi.fn() }));
vi.mock('../lib/institutional-api', () => ({ institutionalRequest: fixture.request }));
vi.mock('../lib/admin-operations-api', () => ({ listRestrictions: fixture.restrictions }));
vi.mock('../lib/use-schedule-workspace', () => ({
  useScheduleWorkspace: () => ({
    context: { period: 'term-1' },
    date: '2026-11-09',
    records: [],
    periods: [],
    loading: false,
    error: '',
    change: vi.fn(),
  }),
}));
import { schedulableRooms } from '../lib/facility-issues';
import { ClassroomRequestsPage } from './ClassroomRequestsPage';
import { TeacherIssueReportPage } from './TeacherIssueReportPage';
import { AlertsFeed } from '../components/scheduling/AlertsFeed';

const room = schedulableRooms[0];
const issue = {
  id: 'issue-1',
  room_id: room.id,
  occurrence_id: null,
  occurrence_date: null,
  category: 'equipment',
  description: 'Invented projector fault',
  status: 'open',
  revision: 1,
  resolution_note: null,
  linked_restriction_id: null,
  created_at: '2026-11-09T08:00:00+08:00',
  updated_at: '2026-11-09T08:00:00+08:00',
  history: [],
};
const request = (id: string, code: string) => ({
  id,
  status: 'rejected',
  revision: 2,
  reason: `Invented reason ${code}`,
  decision_note: 'Invented note',
  created_at: '2026-11-01 08:00:00+08:00',
  updated_at: '2026-11-02 08:00:00+08:00',
  context: {
    class: {
      date: '2026-11-09',
      subject: { code, name: 'Invented seminar' },
      section: { name: 'Invented section' },
      room: { name: 'Original control room' },
    },
    proposed_room: { id: 'other', name: 'Alternate control room' },
  },
});

beforeEach(() => {
  vi.clearAllMocks();
  fixture.restrictions.mockResolvedValue({ restrictions: [] });
});

it('submits a Teacher report with a client key and the chosen room', async () => {
  fixture.request.mockResolvedValue({ issues: [] });
  render(<TeacherIssueReportPage />);
  fireEvent.change(screen.getByLabelText('Room'), { target: { value: room.id } });
  fireEvent.change(screen.getByLabelText('Describe the issue'), {
    target: { value: 'Invented projector fault' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Submit report' }));
  expect(await screen.findByText('Report sent. An Administrator will review it.')).toBeVisible();
  expect(fixture.request).toHaveBeenCalledWith(
    'timetables/issues',
    expect.objectContaining({
      role: 'teacher',
      method: 'POST',
      body: {
        id: expect.any(String),
        room_id: room.id,
        category: 'equipment',
        description: 'Invented projector fault',
      },
    }),
  );
});

it('gives Administrators an issue tab with checked triage and a prefilled restriction link', async () => {
  fixture.request.mockImplementation(async (path: string) =>
    path.endsWith('/transition') ? issue : { requests: [], issues: [issue] },
  );
  render(
    <MemoryRouter initialEntries={['/admin/requests']}>
      <ClassroomRequestsPage role="administrator" />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Issue reports' }));
  expect(await screen.findByText('Invented projector fault')).toBeInTheDocument();
  const link = screen.getByRole('link', { name: `Add a restriction for ${room.name}` });
  const url = new URL(link.getAttribute('href')!, 'http://classsync.test');
  expect(url.pathname).toBe('/admin/buildings/detail');
  expect(url.searchParams.get('room')).toBe(room.id);
  expect(url.searchParams.get('restrict')).toBe('1');
  expect(screen.getByRole('button', { name: 'Mark resolved' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText(`Note for ${room.name}`), {
    target: { value: 'Invented repair' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Mark resolved' }));
  await waitFor(() =>
    expect(fixture.request).toHaveBeenCalledWith(
      'timetables/issues/issue-1/transition',
      expect.objectContaining({
        role: 'administrator',
        body: { expected_revision: 1, status: 'resolved', note: 'Invented repair' },
      }),
    ),
  );
});

it('shows exactly the requested classroom request with its history', async () => {
  fixture.request.mockResolvedValue(request('wanted', 'WANTED1'));
  render(
    <MemoryRouter initialEntries={['/teacher/change-requests/detail?id=wanted']}>
      <ClassroomRequestsPage role="teacher" detail />
    </MemoryRouter>,
  );
  expect(await screen.findByText('Invented reason WANTED1')).toBeInTheDocument();
  expect(screen.getByRole('region', { name: 'Status history' })).toHaveTextContent('Submitted');
  expect(fixture.request).toHaveBeenCalledWith(
    'timetables/requests/wanted',
    expect.objectContaining({ role: 'teacher' }),
  );
});

it.each([
  ['/teacher/change-requests/detail', null],
  ['/teacher/change-requests/detail?id=foreign', 404],
  ['/teacher/change-requests/detail?id=foreign', 200],
])('says not found for %s (%s) without showing another request', async (path, status) => {
  if (status === 404)
    fixture.request.mockRejectedValue(Object.assign(new Error('unavailable'), { status }));
  else fixture.request.mockResolvedValue(request('someone-else', 'OTHER1'));
  render(
    <MemoryRouter initialEntries={[path]}>
      <ClassroomRequestsPage role="teacher" detail />
    </MemoryRouter>,
  );
  expect(
    await screen.findByText('Request not found. It does not exist or it is not yours.'),
  ).toBeInTheDocument();
  expect(screen.queryByText('Invented reason OTHER1')).not.toBeInTheDocument();
});

it('merges class changes with only this audience announcements, newest first', async () => {
  const notice = (id: string, audience: string[], updated_at: string) => ({
    id,
    title: id,
    body: 'Invented body',
    audience,
    updated_at,
  });
  fixture.request.mockResolvedValue({
    announcements: [
      notice('Older notice', ['student'], '2026-11-01T00:00:00Z'),
      notice('Newer notice', ['student'], '2026-11-20T00:00:00Z'),
      notice('Faculty only', ['teacher'], '2026-11-21T00:00:00Z'),
    ],
  });
  render(
    <AlertsFeed
      role="student"
      scheduleReady
      action={() => null}
      changes={[
        {
          id: 'change',
          date: '2026-11-09',
          starts_at: '2026-11-09T08:00:00+08:00',
          ends_at: '2026-11-09T09:00:00+08:00',
          subject: { name: 'Moved seminar' },
          room: { name: 'Control room' },
          section: { name: 'Invented section' },
        } as never,
      ]}
    />,
  );
  await screen.findByText('Newer notice');
  expect(screen.getAllByRole('heading', { level: 3 }).map((item) => item.textContent)).toEqual([
    'Newer notice',
    'Moved seminar',
    'Older notice',
  ]);
  expect(screen.queryByText('Faculty only')).not.toBeInTheDocument();
  expect(fixture.request).toHaveBeenCalledWith(
    'community/announcements',
    expect.objectContaining({ role: 'student' }),
  );
});
