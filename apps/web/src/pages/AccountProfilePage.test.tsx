import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { AccountProfilePage } from './AccountProfilePage';
const fixture = vi.hoisted(() => ({
  profile: {
    uid: 'synthetic-user',
    name: 'Synthetic account',
    email: 'synthetic@example.invalid',
    emailVerified: true,
  },
  update: vi.fn(),
  recover: vi.fn(),
  signOut: vi.fn(),
}));
vi.mock('../auth/account-actions', () => ({
  observeAccountProfile: async (next: (value: unknown) => void) => {
    next(fixture.profile);
    return vi.fn();
  },
  updateAccountName: fixture.update,
  recoverPassword: fixture.recover,
}));
vi.mock('../auth/university-session-context', () => ({
  useUniversitySession: () => ({
    state: { status: 'authorized', membership: { uid: 'synthetic-user', role: 'teacher' } },
    signOut: fixture.signOut,
  }),
}));
beforeEach(() => {
  fixture.profile = {
    uid: 'synthetic-user',
    name: 'Synthetic account',
    email: 'synthetic@example.invalid',
    emailVerified: true,
  };
  fixture.update.mockReset();
  fixture.recover.mockReset();
  fixture.signOut.mockReset();
});
const show = () =>
  render(
    <MemoryRouter>
      <AccountProfilePage role="teacher" />
    </MemoryRouter>,
  );
it('hides account details when the SDK identity does not match current verified membership', async () => {
  fixture.profile.uid = 'other-user';
  show();
  await screen.findByText('Loading your account…');
  expect(screen.queryByText(fixture.profile.email)).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Account name')).not.toBeInTheDocument();
});
it('waits for the confirmed account-name update and exposes no role editor', async () => {
  let complete!: (value: unknown) => void;
  fixture.update.mockImplementation(
    () =>
      new Promise((resolve) => {
        complete = resolve;
      }),
  );
  show();
  fireEvent.change(await screen.findByLabelText('Account name'), {
    target: { value: 'Updated account' },
  });
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Save account name' }));
  await waitFor(() => expect(complete).toBeTypeOf('function'));
  expect(screen.queryByText('Account name saved.')).not.toBeInTheDocument();
  complete({ ...fixture.profile, name: 'Updated account' });
  expect(await screen.findByText('Account name saved.')).toBeInTheDocument();
});
it('reports password recovery failure without pretending an email was sent', async () => {
  fixture.recover.mockRejectedValue(new Error('Offline'));
  show();
  await screen.findByLabelText('Account name');
  fireEvent.click(screen.getByRole('button', { name: 'Send password reset email' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('could not be requested');
  expect(
    screen.queryByText('Password recovery requested. Check your email for the next steps.'),
  ).not.toBeInTheDocument();
});
