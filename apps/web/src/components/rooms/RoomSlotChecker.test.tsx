import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
const fixture = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('../../lib/institutional-api', () => ({ institutionalRequest: fixture.request }));
import { RoomSlotChecker } from './RoomSlotChecker';

const rooms = [
  { id: 'a', name: 'Lab 3', building: 'Main', floor: '2', occupancy: 'free' },
  { id: 'b', name: 'Room 204', building: 'Main', floor: null, occupancy: 'occupied' },
  { id: 'c', name: 'AVR', building: null, floor: null, occupancy: 'restricted' },
];

beforeEach(() => vi.clearAllMocks());

it('checks one aligned slot and filters rooms by availability', async () => {
  fixture.request.mockResolvedValue({ restrictions_checked: false, rooms });
  render(<RoomSlotChecker role="student" period="term-1" initialDate="2026-11-09" />);
  fireEvent.change(screen.getByLabelText('Until'), { target: { value: '600' } });
  fireEvent.click(screen.getByRole('button', { name: 'Check rooms' }));
  expect(await screen.findByRole('status')).toHaveTextContent(
    '1 of 3 rooms have no published class from 08:00 to 10:00.',
  );
  expect(screen.getByRole('status')).toHaveTextContent('Reservations are confirmed');
  expect(fixture.request).toHaveBeenCalledWith(
    'timetables/rooms/term-1/slot?date=2026-11-09&start=480&end=600',
    expect.objectContaining({ role: 'student' }),
  );
  expect(screen.getByText('Reserved')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'No class' }));
  expect(screen.getByText('Lab 3')).toBeInTheDocument();
  expect(screen.queryByText('Room 204')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Occupied' }));
  expect(screen.getByText('Room 204')).toBeInTheDocument();
  expect(screen.getByText('AVR')).toBeInTheDocument();
  expect(screen.queryByText('Lab 3')).not.toBeInTheDocument();
});

it('shows server validation errors without stale results', async () => {
  fixture.request.mockResolvedValueOnce({ restrictions_checked: true, rooms });
  render(<RoomSlotChecker role="administrator" period="term-1" initialDate="2026-11-09" />);
  fireEvent.click(screen.getByRole('button', { name: 'Check rooms' }));
  expect(await screen.findByText('Lab 3')).toBeInTheDocument();
  expect(screen.getByRole('status')).not.toHaveTextContent('Reservations are confirmed');
  fixture.request.mockRejectedValueOnce(new Error('Choose an instructional day in this period.'));
  fireEvent.click(screen.getByRole('button', { name: 'Check rooms' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('instructional day');
  expect(screen.queryByText('Lab 3')).not.toBeInTheDocument();
});

it('keeps the end after the start and labels results with the queried slot', async () => {
  fixture.request.mockResolvedValue({ restrictions_checked: true, rooms });
  render(<RoomSlotChecker role="teacher" period="term-1" initialDate="2026-11-09" />);
  fireEvent.change(screen.getByLabelText('From'), { target: { value: '600' } });
  const until = screen.getByLabelText('Until');
  expect(within(until).getByRole('option', { name: '09:30' })).toBeDisabled();
  expect(until).toHaveValue('630');
  fireEvent.click(screen.getByRole('button', { name: 'Check rooms' }));
  expect(await screen.findByRole('status')).toHaveTextContent('from 10:00 to 10:30');
  fireEvent.change(screen.getByLabelText('From'), { target: { value: '420' } });
  expect(screen.getByRole('status')).toHaveTextContent('from 10:00 to 10:30');
});
