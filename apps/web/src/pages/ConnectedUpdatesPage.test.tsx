import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
const fixture = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('../lib/institutional-api', () => ({ institutionalRequest: fixture.request }));
vi.mock('../lib/use-schedule-workspace', () => ({
  useScheduleWorkspace: () => ({
    context: { period: 'term-1' },
    date: '2026-11-09',
    records: [],
    periods: [{ id: 'term-1', title: 'AY 2026-2027' }],
    loading: false,
    error: '',
    change: vi.fn(),
    retry: vi.fn(),
  }),
}));
import { ConnectedUpdatesPage } from './ConnectedUpdatesPage';

const decided = (id: string, status: string, updated_at: string, note: string | null) => ({
  id,
  status,
  decision_note: note,
  updated_at,
  context: {
    class: { date: '2026-11-09', subject: { code: 'IT 311' }, room: { name: 'Room 201' } },
    proposed_room: { name: 'Lab 3' },
  },
});

beforeEach(() => vi.clearAllMocks());

it('shows the Teacher their latest classroom request decisions, newest first', async () => {
  fixture.request.mockResolvedValue({
    requests: [
      decided('pending', 'pending', '2026-11-03', null),
      decided('older', 'rejected', '2026-11-01', 'Lab reserved'),
      decided('newer', 'fulfilled', '2026-11-02', 'Lab 3 is free'),
    ],
  });
  render(
    <MemoryRouter>
      <ConnectedUpdatesPage role="teacher" />
    </MemoryRouter>,
  );
  const items = await screen.findAllByRole('listitem');
  expect(items).toHaveLength(2);
  expect(items[0]).toHaveTextContent('Approved · new room published');
  expect(items[0]).toHaveTextContent('Room 201 → Lab 3');
  expect(items[1]).toHaveTextContent('Declined');
  expect(items[1]).toHaveTextContent('Note: Lab reserved');
  expect(fixture.request).toHaveBeenCalledWith(
    'timetables/requests',
    expect.objectContaining({ role: 'teacher' }),
  );
});

it('never requests Teacher decisions for students', () => {
  render(
    <MemoryRouter>
      <ConnectedUpdatesPage role="student" />
    </MemoryRouter>,
  );
  expect(fixture.request).not.toHaveBeenCalled();
  expect(screen.queryByText('Classroom request decisions')).not.toBeInTheDocument();
});
