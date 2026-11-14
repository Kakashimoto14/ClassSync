import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { AccountOnboardingPanel } from './AccountOnboardingPanel';
import { UniversitySessionContext } from './university-session-context';
import { MemoryRouter } from 'react-router-dom';

const source = vi.hoisted(() => ({
  request: vi.fn(),
  observe: vi.fn(),
  updateName: vi.fn(),
  resend: vi.fn(),
  refresh: vi.fn(),
}));
vi.mock('./account-actions', () => ({
  accountRequest: source.request,
  observeAccountProfile: source.observe,
  updateAccountName: source.updateName,
  resendVerification: source.resend,
  refreshVerifiedAccount: source.refresh,
  accountError: () => 'Request failed.',
}));
beforeEach(() => {
  vi.clearAllMocks();
  source.request.mockResolvedValue({
    email_verified: true,
    claim_state: null,
    membership_state: null,
    status: 'unlinked',
  });
});

const profile = (uid: string) => ({
  uid,
  name: '',
  email: 'student@synthetic.invalid',
  emailVerified: true,
});

function panel() {
  return (
    <MemoryRouter>
      <UniversitySessionContext.Provider
        value={{ available: true, state: { status: 'denied' }, refresh: vi.fn(), signOut: vi.fn() }}
      >
        <AccountOnboardingPanel />
      </UniversitySessionContext.Provider>
    </MemoryRouter>
  );
}

it('clears student numbers and invitation codes when the Firebase account changes', async () => {
  let next!: (account: ReturnType<typeof profile> | null) => void;
  source.observe.mockImplementation(async (listener) => {
    next = listener;
    listener(profile('student-a'));
    return vi.fn();
  });
  render(panel());
  await screen.findByLabelText('Student number');
  fireEvent.change(screen.getByLabelText('Student number'), {
    target: { value: 'private-previous-number' },
  });
  fireEvent.click(screen.getByText('Have a Teacher invitation?'));
  fireEvent.change(screen.getByLabelText('Invitation code'), {
    target: { value: 'previous-private-token' },
  });
  act(() => next(null));
  expect(screen.queryByLabelText('Student number')).not.toBeInTheDocument();
  act(() => next(profile('student-b')));
  await screen.findByLabelText('Student number');
  expect(screen.getByLabelText('Student number')).toHaveValue('');
  expect(screen.getByLabelText('Invitation code')).toHaveValue('');
});

it('submits only a pending claim and announces confirmation from the server', async () => {
  source.observe.mockImplementation(async (listener) => {
    listener(profile('student-a'));
    return vi.fn();
  });
  source.request.mockImplementation(async (_path, method) =>
    method === 'POST'
      ? { status: 'pending' }
      : { email_verified: true, claim_state: null, membership_state: null, status: 'unlinked' },
  );
  render(panel());
  await screen.findByLabelText('Student number');
  fireEvent.change(screen.getByLabelText('Student number'), {
    target: { value: 'synthetic-student' },
  });
  fireEvent.change(screen.getByLabelText('Account name'), {
    target: { value: 'Synthetic Student' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Review student record' }));
  expect(screen.getByRole('heading', { name: 'Review your student record claim' })).toHaveFocus();
  expect(source.request.mock.calls.some(([, method]) => method === 'POST')).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: 'Request student access' }));
  await waitFor(() =>
    expect(source.request).toHaveBeenCalledWith(
      'student-claims',
      'POST',
      {
        student_id: 'synthetic-student',
      },
      undefined,
      'student-a',
    ),
  );
  expect(source.updateName).toHaveBeenCalledWith('Synthetic Student', 'student-a');
  expect(
    await screen.findByText('Your request is waiting for university verification.'),
  ).toBeInTheDocument();
});
