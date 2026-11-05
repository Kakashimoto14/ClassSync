import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { usePublishedRoomDirectory } from './use-published-room-directory';
const fixture = vi.hoisted(() => ({ state: {} as Record<string, unknown>, request: vi.fn() }));
vi.mock('../auth/university-session-context', () => ({
  useUniversitySession: () => ({ state: fixture.state }),
}));
vi.mock('./institutional-api', () => ({ institutionalRequest: fixture.request }));
const room = {
  id: 'room-a',
  name: 'Invented room',
  building: 'Invented building',
  floor: null,
  location: null,
  room_type: null,
  capacity: null,
  equipment: [],
};
beforeEach(() => {
  fixture.request.mockReset();
  fixture.state = {
    status: 'authorized',
    membership: { uid: 'synthetic-user', role: 'teacher', membership_revision: 1 },
  };
});
it('clears old rooms immediately across publication changes and discards a late response', async () => {
  let complete!: (value: unknown) => void;
  fixture.request
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          complete = resolve;
        }),
    )
    .mockResolvedValue({ version: 'v2', rooms: [{ ...room, id: 'room-new' }] });
  const { result, rerender } = renderHook(
    ({ version }) => usePublishedRoomDirectory('teacher', 'period-a', version),
    { initialProps: { version: 'v1' } },
  );
  rerender({ version: 'v2' });
  await waitFor(() => expect(result.current.rooms[0]?.id).toBe('room-new'));
  await act(async () => complete({ version: 'v1', rooms: [room] }));
  expect(result.current.rooms[0]?.id).toBe('room-new');
});
it('hides all rooms when current membership disappears', async () => {
  fixture.request.mockResolvedValue({ version: 'v1', rooms: [room] });
  const { result, rerender } = renderHook(() =>
    usePublishedRoomDirectory('teacher', 'period-a', 'v1'),
  );
  await waitFor(() => expect(result.current.rooms).toHaveLength(1));
  fixture.state = { status: 'denied' };
  rerender();
  expect(result.current.rooms).toEqual([]);
  expect(result.current.available).toBe(false);
});
it('does not substitute room data after a denied request or publication mismatch', async () => {
  fixture.request
    .mockResolvedValueOnce({ version: 'other-version', rooms: [room] })
    .mockRejectedValueOnce(Object.assign(new Error('Access revoked'), { status: 403 }));
  const { result } = renderHook(() => usePublishedRoomDirectory('teacher', 'period-a', 'v1'));
  await waitFor(() => expect(result.current.error).toContain('timetable changed'));
  expect(result.current.rooms).toEqual([]);
  act(() => result.current.retry());
  await waitFor(() => expect(result.current.error).toBe('Access revoked'));
  expect(result.current.rooms).toEqual([]);
});
