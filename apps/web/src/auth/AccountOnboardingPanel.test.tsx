import { useEffect } from 'react';
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
vi.mock('../auth/TurnstileWidget', () => ({
  TurnstileWidget: ({ onToken }: { onToken: (token: string) => void }) => {
    useEffect(() => onToken('test-token'), [onToken]);
    return <div aria-label="Human verification" />;
  },
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
  source.request.mockImplementation(async (path) => path === 'student-verification-challenges'
    ? { challenge_id: '00000000-0000-0000-0000-000000000001', masked_email: 'j***@student.pnm.edu.ph', expires_in_seconds: 300, resend_after_seconds: 60 }
    : path === 'verify-student'
      ? { status: 'verified' }
      : path === 'complete-student-onboarding'
        ? { status: 'active', password_configured: true }
      : { email_verified: true, claim_state: null, membership_state: null, status: 'unlinked' });
  render(panel(refresh));
  await screen.findByLabelText('Student number');
  fireEvent.change(screen.getByLabelText('Student number'), {
    target: { value: '24-98096' },
  });
  expect(screen.getByLabelText('Registered student email')).toHaveValue(
    'juan.delacruz@student.pnm.edu.ph',
  );
  fireEvent.click(screen.getByRole('button', { name: 'Send verification code' }));
  await waitFor(() =>
    expect(source.request).toHaveBeenCalledWith(
      'student-verification-challenges',
      'POST',
      {
        student_id: '24-98096',
        turnstile_token: 'test-token',
      },
      undefined,
      'student-a',
    ),
  );
  expect(await screen.findByText(/A code was sent to j\*\*\*/)).toBeInTheDocument();
  for (let index = 0; index < 6; index += 1)
    fireEvent.change(screen.getByLabelText(`Verification digit ${index + 1}`), {
      target: { value: String(index + 1) },
    });
  fireEvent.click(screen.getByRole('button', { name: 'Verify and sign in' }));
  await waitFor(() => expect(source.request).toHaveBeenCalledWith(
    'verify-student', 'POST', {
      student_id: '24-98096', challenge_id: '00000000-0000-0000-0000-000000000001', code: '123456',
      turnstile_token: 'test-token',
    }, undefined, 'student-a',
  ));
  expect(await screen.findByRole('heading', { name: 'Create your portal password' })).toBeInTheDocument();
  expect(screen.getByText('24-98096')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'Campus-pass-2026!' } });
  fireEvent.change(screen.getByLabelText('Confirm Password'), { target: { value: 'Campus-pass-2026!' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create portal password' }));
  await waitFor(() => expect(source.request).toHaveBeenCalledWith(
    'complete-student-onboarding', 'POST', {
      student_id: '24-98096', challenge_id: '00000000-0000-0000-0000-000000000001',
      turnstile_token: 'test-token', password: 'Campus-pass-2026!',
    }, undefined, 'student-a',
  ));
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
  fireEvent.click(screen.getByRole('button', { name: 'Send verification code' }));
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
  fireEvent.click(screen.getByRole('button', { name: 'Send verification code' }));
  expect(await screen.findByRole('status')).toHaveTextContent(/Use the format 12-12345/);
  expect(screen.getByText(/Use the format 12-12345/, { selector: '#student-number-error' }))
    .toBeInTheDocument();
  expect(source.request).not.toHaveBeenCalledWith(
    'student-verification-challenges', expect.anything(), expect.anything(), expect.anything(), expect.anything(),
  );
});
