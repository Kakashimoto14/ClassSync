import { useEffect } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AccountOnboardingPanel } from './AccountOnboardingPanel';
import { UniversitySessionContext } from './university-session-context';
import { MemoryRouter } from 'react-router-dom';
import { cooldownRemaining, RateLimitError, startCooldown } from './cooldown';

const source = vi.hoisted(() => ({
  request: vi.fn(),
  observe: vi.fn(),
  updateName: vi.fn(),
  resend: vi.fn(),
  refresh: vi.fn(),
  turnstileReady: true,
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
    useEffect(() => {
      if (source.turnstileReady) onToken('test-token');
    }, [onToken]);
    return <button type="button" onClick={() => onToken('test-token')}>Complete human verification</button>;
  },
}));
beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  source.turnstileReady = true;
  source.request.mockResolvedValue({
    email_verified: true,
    claim_state: null,
    membership_state: null,
    status: 'unlinked',
    verification_mode: 'cor_or_roster',
  });
});
afterEach(() => vi.useRealTimers());

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
    ? { challenge_id: '00000000-0000-0000-0000-000000000001', masked_email: 's***@gmail.com', expires_in_seconds: 300, resend_after_seconds: 30 }
    : path === 'verify-student'
      ? { status: 'verified' }
      : path === 'complete-student-onboarding'
        ? { status: 'active', password_configured: true }
      : { email_verified: true, claim_state: null, membership_state: null, status: 'unlinked', verification_mode: 'cor_or_roster' });
  render(panel(refresh));
  await screen.findByLabelText('Student number');
  fireEvent.change(screen.getByLabelText('Student number'), {
    target: { value: '24-98096' },
  });
  expect(screen.getByLabelText('Email address')).toHaveValue(
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
  expect(await screen.findByText(/A code was sent to s\*\*\*@gmail\.com/)).toBeInTheDocument();
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

it('offers the Registration Form path when the roster has no matching record', async () => {
  source.observe.mockImplementation(async (listener) => {
    listener(profile('student-a'));
    return vi.fn();
  });
  source.request.mockImplementation(async (_path, method) => {
    if (method === 'POST') throw new Error('No matching active student record was found. Scan your Registration Form or contact the Registrar.');
    return { email_verified: true, claim_state: null, membership_state: null, status: 'unlinked', verification_mode: 'cor_or_roster' };
  });
  render(panel());
  await screen.findByLabelText('Student number');
  fireEvent.change(screen.getByLabelText('Student number'), { target: { value: '24-98096' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send verification code' }));
  expect(await screen.findByRole('link', { name: 'Scan Registration Form (COR)' })).toBeInTheDocument();
});

it('shows the completed email step and uses an email-neutral placeholder', async () => {
  source.observe.mockImplementation(async (listener) => {
    listener(profile('student-a'));
    return vi.fn();
  });
  render(panel());
  await screen.findByLabelText('Student number');
  expect(screen.getByText('Step 1 · Email verified')).toBeInTheDocument();
  expect(screen.getByText('Step 2 of 2 · Confirm Registration Form')).toBeInTheDocument();
  expect(screen.getByLabelText('Email address')).toHaveAttribute('placeholder', 'student@example.com');
});

it('keeps validation and missing human verification errors reachable from submit', async () => {
  source.turnstileReady = false;
  source.observe.mockImplementation(async (listener) => {
    listener(profile('student-a'));
    return vi.fn();
  });
  render(panel());
  await screen.findByLabelText('Student number');
  fireEvent.change(screen.getByLabelText('Student number'), { target: { value: 'student-a' } });
  const send = screen.getByRole('button', { name: 'Send verification code' });
  expect(send).toBeEnabled();
  fireEvent.click(send);
  expect(await screen.findByRole('status')).toHaveTextContent('Use the format 12-12345 for your student number.');
  fireEvent.change(screen.getByLabelText('Student number'), { target: { value: '24-98096' } });
  fireEvent.click(send);
  expect(await screen.findByText('Complete the human verification check before continuing.')).toBeInTheDocument();
  expect(source.request).not.toHaveBeenCalledWith(
    'student-verification-challenges', expect.anything(), expect.anything(), expect.anything(), expect.anything(),
  );
});

it('does not write a verification-email cooldown for a generic status action rate limit', async () => {
  source.observe.mockImplementation(async (listener) => {
    listener(profile('student-a'));
    return vi.fn();
  });
  render(panel());
  await screen.findByLabelText('Student number');
  source.request.mockRejectedValueOnce(new RateLimitError('Please wait.', 19));
  fireEvent.click(screen.getByRole('button', { name: 'Check account status' }));
  await screen.findByText('Please wait.');
  expect(cooldownRemaining('verification-email', profile('student-a').email)).toBe(0);
});

it('stores a resend Retry-After only in the verification email cooldown', async () => {
  source.observe.mockImplementation(async (listener) => {
    listener(profile('student-a'));
    return vi.fn();
  });
  source.request.mockResolvedValue({
    email_verified: false, claim_state: null, membership_state: null,
    status: 'verify-email', verification_mode: 'cor_or_roster',
  });
  source.resend.mockRejectedValueOnce(new RateLimitError('Please wait before requesting another email.', 19));
  render(panel());
  const resend = await screen.findByRole('button', { name: 'Resend verification email' });
  fireEvent.click(resend);
  await screen.findByText('Please wait before requesting another email.');
  expect(cooldownRemaining('verification-email', profile('student-a').email)).toBe(19);
  expect(cooldownRemaining('student-code', profile('student-a').email)).toBe(0);
});

it('recomputes both persisted onboarding cooldowns while same-second ticks continue', async () => {
  vi.useFakeTimers();
  const start = new Date('2026-11-21T00:00:00Z');
  vi.setSystemTime(start);
  startCooldown('verification-email', profile('student-a').email, 2);
  startCooldown('student-code', profile('student-a').email, 4);
  let verified = false;
  source.observe.mockImplementation(async (listener) => {
    listener(profile('student-a'));
    return vi.fn();
  });
  source.request.mockImplementation(async (path: string) => path === 'onboarding'
    ? { email_verified: verified, membership_state: null, claim_state: null,
        status: verified ? 'unlinked' : 'verify-email', verification_mode: 'cor_or_roster' }
    : undefined);
  source.refresh.mockImplementation(async () => { verified = true; });
  render(panel());
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(screen.getByRole('button', { name: 'Resend verification email in 2s' })).toBeDisabled();
  await act(async () => { vi.advanceTimersByTime(500); });
  expect(screen.getByRole('button', { name: 'Resend verification email in 2s' })).toBeDisabled();
  await act(async () => { vi.advanceTimersByTime(1500); });
  expect(screen.getByRole('button', { name: 'Resend verification email' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'I verified my email' }));
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
  expect(screen.getByRole('button', { name: 'Send verification code in 2s' })).toBeDisabled();
  await act(async () => { vi.advanceTimersByTime(500); });
  expect(screen.getByRole('button', { name: 'Send verification code in 2s' })).toBeDisabled();
  await act(async () => { vi.advanceTimersByTime(1500); });
  expect(screen.getByRole('button', { name: 'Send verification code' })).toBeEnabled();
});

it('re-syncs the verification-email cooldown when the Firebase profile email changes', async () => {
  let updateProfile!: (next: ReturnType<typeof profile> | null) => void;
  source.observe.mockImplementation(async (listener) => {
    updateProfile = listener;
    listener(profile('student-a'));
    return vi.fn();
  });
  source.request.mockResolvedValue({
    email_verified: false, claim_state: null, membership_state: null,
    status: 'verify-email', verification_mode: 'cor_or_roster',
  });
  startCooldown('verification-email', 'new.address@example.com', 23);
  render(panel());
  await screen.findByRole('button', { name: 'Resend verification email' });
  act(() => updateProfile({ ...profile('student-a'), email: 'new.address@example.com' }));
  expect(await screen.findByRole('button', { name: 'Resend verification email in 23s' })).toBeDisabled();
});

it('re-syncs the student-code cooldown when the Firebase profile email changes', async () => {
  let updateProfile!: (next: ReturnType<typeof profile> | null) => void;
  source.observe.mockImplementation(async (listener) => {
    updateProfile = listener;
    listener(profile('student-a'));
    return vi.fn();
  });
  source.request.mockResolvedValue({
    email_verified: true, claim_state: null, membership_state: null,
    status: 'unlinked', verification_mode: 'cor_or_roster',
  });
  startCooldown('student-code', 'new.address@example.com', 23);
  render(panel());
  await screen.findByLabelText('Student number');
  act(() => updateProfile({ ...profile('student-a'), email: 'new.address@example.com' }));
  expect(await screen.findByRole('button', { name: 'Send verification code in 23s' })).toBeDisabled();
});

it('surfaces missing Turnstile feedback for OTP and password setup instead of disabling submit', async () => {
  let verified = false;
  source.turnstileReady = true;
  source.observe.mockImplementation(async (listener) => {
    listener(profile('student-a'));
    return vi.fn();
  });
  source.request.mockImplementation(async (path: string) => {
    if (path === 'onboarding') return {
      email_verified: true, membership_state: null, claim_state: null,
      status: 'unlinked', verification_mode: 'cor_or_roster',
    };
    if (path === 'student-verification-challenges') {
      source.turnstileReady = false;
      return {
        challenge_id: 'challenge-1', masked_email: 's***@example.com',
        expires_in_seconds: 300, resend_after_seconds: 30,
      };
    }
    if (path === 'verify-student') {
      verified = true;
      source.turnstileReady = false;
      return { status: 'verified' };
    }
    return undefined;
  });
  render(panel());
  await screen.findByLabelText('Student number');
  fireEvent.change(screen.getByLabelText('Student number'), { target: { value: '23-01425' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send verification code' }));
  await screen.findByText(/A code was sent/);
  for (let index = 0; index < 6; index += 1)
    fireEvent.change(screen.getByLabelText(`Verification digit ${index + 1}`), {
      target: { value: String(index + 1) },
    });
  const verify = screen.getByRole('button', { name: 'Verify and sign in' });
  expect(verify).toBeEnabled();
  fireEvent.click(verify);
  expect(await screen.findByRole('status')).toHaveTextContent('Complete the human verification check');
  expect(source.request).not.toHaveBeenCalledWith('verify-student', expect.anything(), expect.anything(), expect.anything(), expect.anything());

  fireEvent.click(screen.getByRole('button', { name: 'Complete human verification' }));
  fireEvent.click(verify);
  await screen.findByRole('heading', { name: 'Create your portal password' });
  fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'Campus-pass-2026!' } });
  fireEvent.change(screen.getByLabelText('Confirm Password'), { target: { value: 'Campus-pass-2026!' } });
  const complete = screen.getByRole('button', { name: 'Create portal password' });
  expect(complete).toBeEnabled();
  fireEvent.click(complete);
  expect(await screen.findByRole('status')).toHaveTextContent('Complete the human verification check');
  expect(verified).toBe(true);
  expect(source.request).not.toHaveBeenCalledWith('complete-student-onboarding', expect.anything(), expect.anything(), expect.anything(), expect.anything());
});
