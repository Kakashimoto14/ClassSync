import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { AccountAdministrationPanel } from './AccountAdministrationPanel';

const source = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock('./account-actions', () => ({ accountRequest: source.request }));

const student = {
  uid: 'student-uid',
  student_id: '23-01425',
  registered_email: 'student@example.com',
  verification_source: 'cor_self_verified',
  membership_revision: 4,
};

beforeEach(() => {
  vi.clearAllMocks();
  source.request.mockImplementation(async (path: string) => {
    if (path === 'student-claims' || path === 'faculty-records') return [];
    if (path === 'self-verified-students') return [student];
    return undefined;
  });
});

function panel() {
  return render(<MemoryRouter><AccountAdministrationPanel uid="admin-uid" /></MemoryRouter>);
}

it('requires a row-level confirmation before revoking and preserves the named success message', async () => {
  panel();
  fireEvent.click(screen.getByRole('button', { name: 'Load account requests' }));
  await screen.findByText('23-01425');
  await waitFor(() => expect(screen.getByRole('button', { name: 'Revoke access' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Revoke access' }));
  expect(screen.getByText(/Revoke access for student 23-01425\?/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Cancel revoke' }));
  expect(source.request).not.toHaveBeenCalledWith(
    'memberships/student-uid/revoke', 'PATCH', expect.anything(), expect.anything(), expect.anything(),
  );

  fireEvent.click(screen.getByRole('button', { name: 'Revoke access' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm revoke' }));

  await waitFor(() => expect(source.request).toHaveBeenCalledWith(
    'memberships/student-uid/revoke', 'PATCH', { expected_revision: 4 }, undefined, 'admin-uid',
  ));
  expect(await screen.findByRole('status')).toHaveTextContent('Access revoked for student 23-01425.');
});
