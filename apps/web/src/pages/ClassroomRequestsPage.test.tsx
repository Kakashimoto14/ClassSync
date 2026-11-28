import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
const fixture = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('../lib/institutional-api', () => ({ institutionalRequest: fixture.request }));
vi.mock('../lib/use-schedule-workspace', () => ({
  useScheduleWorkspace: () => ({
    context: { period: 'owned-period' },
    date: '2026-11-09',
    records: [request.context.class],
    periods: [{ id: 'owned-period', title: 'Invented term' }],
    data: { version: 'owned-version' },
    loading: false,
    error: '',
    change: vi.fn(),
  }),
}));
import { ClassroomRequestsPage } from './ClassroomRequestsPage';
const request = {
  id: 'owned-request',
  period_id: 'owned-period',
  publication_id: 'owned-version',
  draft_id: 'private-admin-draft',
  status: 'pending',
  revision: 1,
  reason: 'Invented classroom request',
  decision_note: null,
  context: {
    class: {
      id: 'owned-class',
      date: '2026-11-09',
      subject: { code: 'TEST101', name: 'Invented seminar' },
      section: { name: 'Invented section' },
      room: { name: 'Original control room' },
    },
    proposed_room: { id: 'other-room', name: 'Alternate control room' },
  },
};
beforeEach(() => {
  vi.clearAllMocks();
  fixture.request.mockResolvedValue({ requests: [request] });
});
const respond = (overrides: Record<string, unknown> = {}) =>
  fixture.request.mockImplementation(async (path: string) => {
    if (path.endsWith('/preflight')) return overrides.preflight ?? { state: 'clear', reasons: [] };
    if (path.endsWith('/decision')) {
      if (overrides.decision instanceof Error) throw overrides.decision;
      return overrides.decision ?? { ...request, status: 'fulfilled', revision: 3 };
    }
    return { requests: [request] };
  });
it('approves only after a clear live check and reports the published change', async () => {
  respond();
  render(
    <MemoryRouter>
      <ClassroomRequestsPage role="administrator" />
    </MemoryRouter>,
  );
  expect(await screen.findByText('No conflicts')).toBeInTheDocument();
  expect(fixture.request).toHaveBeenCalledWith(
    'timetables/requests/owned-request/preflight',
    expect.objectContaining({ role: 'administrator' }),
  );
  fireEvent.change(screen.getByLabelText('Decision note for TEST101'), {
    target: { value: 'Approved synthetic control for publication review' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Approve and publish change' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Classroom change published');
  expect(fixture.request).toHaveBeenCalledWith(
    'timetables/requests/owned-request/decision',
    expect.objectContaining({
      role: 'administrator',
      method: 'POST',
      body: {
        expected_revision: 1,
        decision: 'approved',
        note: 'Approved synthetic control for publication review',
      },
    }),
  );
  expect(screen.queryByRole('link', { name: 'Review classroom change' })).not.toBeInTheDocument();
});
it('blocks approval while the live check reports a conflict but still allows declining', async () => {
  respond({ preflight: { state: 'conflict', reasons: ['Room conflict between a and b.'] } });
  render(
    <MemoryRouter>
      <ClassroomRequestsPage role="administrator" />
    </MemoryRouter>,
  );
  expect(await screen.findByText('Conflict found')).toBeInTheDocument();
  expect(screen.getByText(/Room conflict between a and b\./)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Decision note for TEST101'), {
    target: { value: 'Room is double booked' },
  });
  expect(screen.getByRole('button', { name: 'Approve and publish change' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Decline request' })).toBeEnabled();
});
it('re-checks conflicts after an approval is rejected by the server', async () => {
  respond({
    decision: Object.assign(new Error('The proposed room is now occupied at this class time.'), {
      status: 409,
    }),
  });
  render(
    <MemoryRouter>
      <ClassroomRequestsPage role="administrator" />
    </MemoryRouter>,
  );
  await screen.findByText('No conflicts');
  fireEvent.change(screen.getByLabelText('Decision note for TEST101'), {
    target: { value: 'Approve this change' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Approve and publish change' }));
  await waitFor(() =>
    expect(screen.getByRole('alert')).toHaveTextContent('now occupied at this class time'),
  );
  await waitFor(() =>
    expect(
      fixture.request.mock.calls.filter(([path]) => String(path).endsWith('/preflight')),
    ).toHaveLength(2),
  );
});
it('clears the previous request list when refreshed access is denied', async () => {
  render(
    <MemoryRouter>
      <ClassroomRequestsPage role="teacher" />
    </MemoryRouter>,
  );
  await screen.findByText('Invented classroom request');
  fixture.request.mockRejectedValue(new Error('Current membership required'));
  fireEvent.click(screen.getByRole('button', { name: 'Reload requests' }));
  await screen.findByRole('alert');
  expect(screen.queryByText('Invented classroom request')).not.toBeInTheDocument();
});
it('keeps a failed decision unconfirmed and permits a deliberate reload', async () => {
  render(
    <MemoryRouter>
      <ClassroomRequestsPage role="administrator" />
    </MemoryRouter>,
  );
  fireEvent.change(await screen.findByLabelText('Decision note for TEST101'), {
    target: { value: 'Invented local decision' },
  });
  fixture.request.mockRejectedValue(new Error('This request changed. Reload before deciding.'));
  fireEvent.click(screen.getByRole('button', { name: 'Approve and publish change' }));
  await waitFor(() =>
    expect(screen.getAllByRole('alert')[0]).toHaveTextContent('request changed'),
  );
  expect(screen.queryByRole('link', { name: 'Review classroom change' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Reload requests' })).toBeEnabled();
});

it('filters Administrator requests with counted status pills', async () => {
  render(<MemoryRouter><ClassroomRequestsPage role="administrator" /></MemoryRouter>);
  await screen.findByText('Invented classroom request');
  expect(screen.getByRole('button', { name: /All 1/ })).toHaveAttribute('aria-pressed', 'true');
  fireEvent.click(screen.getByRole('button', { name: /Not approved 0/ }));
  expect(await screen.findByText('No requests match this status.')).toBeInTheDocument();
  expect(screen.queryByText('Invented classroom request')).not.toBeInTheDocument();
});

it('labels the classroom selector exactly and waits for confirmed submission before navigating', async () => {
  let complete!: (value: unknown) => void;
  fixture.request.mockImplementation((_path, options) =>
    options?.method === 'POST'
      ? new Promise((resolve) => {
          complete = resolve;
        })
      : Promise.resolve({
          publication_id: 'owned-version',
          rooms: [{ id: 'approved-room', name: 'Approved control room' }],
        }),
  );
  render(
    <MemoryRouter initialEntries={['/new']}>
      <Routes>
        <Route path="/new" element={<ClassroomRequestsPage role="teacher" create />} />
        <Route path="/teacher/change-requests" element={<p>Confirmed request list</p>} />
      </Routes>
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByRole('combobox', { name: 'Published class' }), {
    target: { value: 'owned-class' },
  });
  const selector = await screen.findByRole('combobox', { name: 'Proposed classroom' });
  expect(screen.getByLabelText('Proposed classroom', { exact: true })).toBe(selector);
  fireEvent.change(selector, { target: { value: 'approved-room' } });
  fireEvent.change(screen.getByRole('textbox', { name: 'Reason for change' }), {
    target: { value: 'Invented classroom change' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Submit classroom request' }));
  await waitFor(() => expect(complete).toBeTypeOf('function'));
  expect(screen.queryByText('Confirmed request list')).not.toBeInTheDocument();
  await act(async () => complete({ id: 'server-confirmed-request' }));
  expect(await screen.findByText('Confirmed request list')).toBeInTheDocument();
});

it('labels room occupancy, disables occupied rooms and refreshes after a 409', async () => {
  let options = 0;
  fixture.request.mockImplementation(async (_path: string, init?: { method?: string }) => {
    if (init?.method === 'POST')
      throw Object.assign(new Error('That room is occupied at this class time. Choose another room.'), {
        status: 409,
      });
    options += 1;
    return {
      publication_id: 'owned-version',
      rooms: [
        { id: 'free-room', name: 'Lab 3', capacity: 40, occupancy: 'available' },
        { id: 'busy-room', name: 'Room 204', capacity: null, occupancy: 'occupied' },
      ],
    };
  });
  render(
    <MemoryRouter>
      <ClassroomRequestsPage role="teacher" create />
    </MemoryRouter>,
  );
  fireEvent.change(screen.getByRole('combobox', { name: 'Published class' }), {
    target: { value: 'owned-class' },
  });
  expect(await screen.findByRole('option', { name: 'Lab 3 · 40 seats · Available' })).toBeEnabled();
  expect(screen.getByRole('option', { name: 'Room 204 · Occupied' })).toBeDisabled();
  expect(screen.getByRole('status')).toHaveTextContent(
    '1 of 2 eligible rooms are available at this class time.',
  );
  fireEvent.change(screen.getByRole('combobox', { name: 'Proposed classroom' }), {
    target: { value: 'free-room' },
  });
  fireEvent.change(screen.getByRole('textbox', { name: 'Reason for change' }), {
    target: { value: 'Projector is broken' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Submit classroom request' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('occupied at this class time');
  await waitFor(() => expect(options).toBe(2));
});
