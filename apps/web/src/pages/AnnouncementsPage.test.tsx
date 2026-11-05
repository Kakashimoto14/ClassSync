import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { AnnouncementsPage } from './AnnouncementsPage';
const request = vi.hoisted(() => vi.fn());
vi.mock('../lib/institutional-api', () => ({ institutionalRequest: request }));
const row = {
  id: 'notice-a',
  title: 'Synthetic notice',
  body: '<script>not executable</script>',
  audience: ['teacher'],
  revision: 2,
  updated_at: '2026-11-05T00:00:00Z',
};
beforeEach(() => request.mockReset());
it('shows only supplied notices as text and gives Teachers no management controls', async () => {
  request.mockResolvedValue({ announcements: [row] });
  const { container } = render(<AnnouncementsPage role="teacher" />);
  expect(await screen.findByText(row.body)).toBeInTheDocument();
  expect(container.querySelector('script')).toBeNull();
  expect(screen.queryByText('Create announcement')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /Archive/ })).not.toBeInTheDocument();
});
it('clears previously visible notices when refreshing loses access', async () => {
  request
    .mockResolvedValueOnce({ announcements: [row] })
    .mockRejectedValueOnce(Object.assign(new Error('Access revoked'), { status: 403 }));
  render(<AnnouncementsPage role="teacher" />);
  await screen.findByText(row.title);
  fireEvent.click(screen.getByRole('button', { name: 'Refresh announcements' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Access revoked');
  expect(screen.queryByText(row.body)).not.toBeInTheDocument();
});
it('keeps the revision-bound edit pending until the server confirms it', async () => {
  let complete!: (value: unknown) => void;
  request
    .mockResolvedValueOnce({ announcements: [row] })
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          complete = resolve;
        }),
    )
    .mockResolvedValue({ announcements: [{ ...row, title: 'Updated notice' }] });
  render(<AnnouncementsPage role="administrator" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Edit Synthetic notice' }));
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'Updated notice' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save announcement' }));
  await waitFor(() => expect(complete).toBeTypeOf('function'));
  expect(request).toHaveBeenLastCalledWith(
    'community/announcements/notice-a',
    expect.objectContaining({
      method: 'PATCH',
      body: expect.objectContaining({ expected_revision: 2, title: 'Updated notice' }),
    }),
  );
  expect(screen.queryByText('Announcement updated.')).not.toBeInTheDocument();
  complete({ ...row, title: 'Updated notice', revision: 3 });
  expect(await screen.findByText('Announcement updated.')).toBeInTheDocument();
});
