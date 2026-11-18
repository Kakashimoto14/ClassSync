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
it('records an Administrator decision without claiming a classroom is already published', async () => {
  fixture.request.mockImplementation(async (path) =>
    path.endsWith('/decision')
      ? { ...request, status: 'approved', revision: 2 }
      : { requests: [request] },
  );
  render(
    <MemoryRouter>
      <ClassroomRequestsPage role="administrator" />
    </MemoryRouter>,
  );
  fireEvent.change(await screen.findByLabelText('Decision note for TEST101'), {
    target: { value: 'Approved synthetic control for publication review' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Approve for publication' }));
  await screen.findByRole('link', { name: 'Review classroom change' });
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
  expect(screen.getByRole('button', { name: /Classroom change published/ })).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Approved · awaiting publication');
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
  fireEvent.click(screen.getByRole('button', { name: 'Approve for publication' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('request changed'));
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
