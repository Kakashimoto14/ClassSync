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
  email: 'juan.delacruz@student.pnm.edu.ph',
  emailVerified: true,
});

function panel(refresh = vi.fn()) {
  return (
    <MemoryRouter>
      <UniversitySessionContext.Provider
        value={{ available: true, state: { status: 'denied' }, refresh, signOut: vi.fn() }}
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
  expect(screen.getByLabelText('Student number')).toHaveAttribute('placeholder', '12-12345');
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
  expect(screen.getByLabelText('Student number')).toHaveAttribute('placeholder', '12-12345');
  expect(screen.getByLabelText('Student number')).toHaveValue('');
  expect(screen.getByLabelText('Invitation code')).toHaveValue('');
});

it('checks student ID against the verified account email and refreshes current membership', async () => {
  const refresh = vi.fn();
  source.observe.mockImplementation(async (listener) => {
    listener(profile('student-a'));
    return vi.fn();
  });
  source.request.mockImplementation(async (_path, method) => method === 'POST'
    ? { status: 'verified' }
    : { email_verified: true, claim_state: null, membership_state: null, status: 'unlinked' });
  render(panel(refresh));
  await screen.findByLabelText('Student number');
  fireEvent.change(screen.getByLabelText('Student number'), {
    target: { value: '24-98096' },
  });
  expect(screen.getByLabelText('Registered student email')).toHaveValue(
    'juan.delacruz@student.pnm.edu.ph',
  );
  fireEvent.click(screen.getByRole('button', { name: 'Verify student record' }));
  await waitFor(() =>
    expect(source.request).toHaveBeenCalledWith(
      'verify-student',
      'POST',
      {
        student_id: '24-98096',
      },
      undefined,
      'student-a',
    ),
  );
  expect(
    await screen.findByText('Student record verified. Refresh your account to continue.'),
  ).toBeInTheDocument();
  expect(source.updateName).not.toHaveBeenCalled();
  expect(refresh).toHaveBeenCalledOnce();
});

it('shows the exact anti-enumeration Registrar error for a roster mismatch', async () => {
  source.observe.mockImplementation(async (listener) => {
    listener(profile('student-a'));
    return vi.fn();
  });
  const registrarError =
    'Unable to sign in wth Google. Use the email registered in your student record. If you need assistance, contact the Registrar';
  source.request.mockImplementation(async (_path, method) => {
    if (method === 'POST') throw new Error(registrarError);
    return { email_verified: true, claim_state: null, membership_state: null, status: 'unlinked' };
  });
  render(panel());
  await screen.findByLabelText('Student number');
  fireEvent.change(screen.getByLabelText('Student number'), { target: { value: '24-98096' } });
  fireEvent.click(screen.getByRole('button', { name: 'Verify student record' }));
  expect(await screen.findByText(registrarError)).toBeInTheDocument();
});

it('rejects malformed student IDs in the form before sending a roster lookup', async () => {
  source.observe.mockImplementation(async (listener) => {
    listener(profile('student-a'));
    return vi.fn();
  });
  render(panel());
  await screen.findByLabelText('Student number');
  fireEvent.change(screen.getByLabelText('Student number'), { target: { value: 'student-a' } });
  fireEvent.click(screen.getByRole('button', { name: 'Verify student record' }));
  expect(await screen.findByRole('status')).toHaveTextContent(/Use the format 12-12345/);
  expect(screen.getByText(/Use the format 12-12345/, { selector: '#student-number-error' }))
    .toBeInTheDocument();
  expect(source.request).not.toHaveBeenCalledWith(
    'verify-student', expect.anything(), expect.anything(), expect.anything(), expect.anything(),
  );
});
