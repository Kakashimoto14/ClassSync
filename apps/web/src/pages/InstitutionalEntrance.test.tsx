import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { InstitutionalEntrance } from './InstitutionalEntrance';
import { cooldownRemaining, RateLimitError, startCooldown } from '../auth/cooldown';
import {
  UniversitySessionContext,
  type UniversitySessionContextValue,
} from '../auth/university-session-context';

const actions = vi.hoisted(() => ({
  create: vi.fn(), recover: vi.fn(), signIn: vi.fn(), google: vi.fn(),
  verifyGoogle: vi.fn(),
  verify: vi.fn().mockResolvedValue(undefined), resetVerify: vi.fn(), resetComplete: vi.fn(),
}));
vi.mock('../auth/account-actions', async (original) => ({
  ...(await original<typeof import('../auth/account-actions')>()),
  createStudentAccount: actions.create,
  recoverPassword: actions.recover,
  signInToAccount: actions.signIn,
  signInWithGoogle: actions.google,
  verifyGoogleSignIn: actions.verifyGoogle,
  verifyHumanChallenge: actions.verify,
  verifyPasswordResetCode: actions.resetVerify,
  completePasswordReset: actions.resetComplete,
}));
vi.mock('../auth/TurnstileWidget', async () => {
  const React = await import('react');
  return {
    TurnstileWidget: React.forwardRef<
      { reset: () => void },
      { onToken: (token: string) => void }
    >(function TestTurnstile({ onToken }, ref) {
      React.useImperativeHandle(ref, () => ({ reset: () => onToken('') }), [onToken]);
      return (
        <button type="button" onClick={() => onToken('test-token')}>
          Complete human verification
        </button>
      );
    }),
  };
});

function completeHumanVerification() {
  fireEvent.click(screen.getByRole('button', { name: 'Complete human verification' }));
}

function entrance(path = '/', overrides: Partial<UniversitySessionContextValue> = {}) {
  const refresh = vi.fn();
  render(
    <UniversitySessionContext.Provider
      value={{
        available: true,
        state: { status: 'signed-out' },
        refresh,
        signOut: vi.fn(),
        ...overrides,
      }}
    >
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/student/dashboard" element={<h1>Student workspace</h1>} />
          <Route path="*" element={<InstitutionalEntrance />} />
        </Routes>
      </MemoryRouter>
    </UniversitySessionContext.Provider>,
  );
  return refresh;
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
});
afterEach(() => vi.useRealTimers());

it('shows the CdM campus access login and a non-production verification widget', async () => {
  entrance();
  expect(screen.getByRole('heading', { name: 'Welcome to ClassSync' })).toBeInTheDocument();
  expect(screen.getByText('CAMPUS ACCESS')).toBeInTheDocument();
  expect(screen.getAllByText('Signing in for the first time?')).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Complete human verification' })).toBeInTheDocument();
  expect(screen.queryByText(/sample agenda/i)).not.toBeInTheDocument();
  const google = screen.getByRole('button', { name: 'Continue with Google' });
  expect(google.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
});

it('prewarms the Gateway health endpoint without blocking the login form', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    status: 200,
  } as Response);
  entrance();

  await waitFor(() => expect(fetch).toHaveBeenCalledWith(
    expect.stringMatching(/\/api\/v1\/health$/),
    expect.objectContaining({ method: 'GET', credentials: 'omit', cache: 'no-store' }),
  ));
  fetch.mockRestore();
});

it('offers one login, refreshes the server-authorized session after sign-in, and keeps labels associated', async () => {
  const refresh = entrance();
  for (const name of ['Student', 'Teacher', 'Admin'])
    expect(screen.queryByRole('button', { name })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign in to ClassSync →' })).toBeEnabled();
  expect(screen.getByLabelText('Student Number or Email')).toBeRequired();
  fireEvent.click(screen.getByRole('button', { name: 'Sign in to ClassSync →' }));
  expect(await screen.findByText('Enter your student number or email address.')).toBeInTheDocument();
  expect(screen.getByText('Enter your password.')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Student Number or Email'), {
    target: { value: ' Student.Demo@Example.com ' },
  });
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'Synthetic-password-42!' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
  expect(screen.getByRole('button', { name: 'Show password' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  completeHumanVerification();
  fireEvent.click(screen.getByRole('button', { name: 'Sign in to ClassSync →' }));
  await waitFor(() =>
    expect(actions.signIn).toHaveBeenCalledWith(
      'student.demo@example.com',
      'Synthetic-password-42!',
    ),
  );
  expect(refresh).toHaveBeenCalledOnce();
});

it('routes student-number sign-in through the Gateway with the one-use Turnstile token', async () => {
  entrance();
  fireEvent.change(screen.getByLabelText('Student Number or Email'), {
    target: { value: '23-01425' },
  });
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'campus-pass-2026' },
  });
  completeHumanVerification();
  fireEvent.click(screen.getByRole('button', { name: 'Sign in to ClassSync →' }));

  await waitFor(() => expect(actions.signIn).toHaveBeenCalledWith(
    '23-01425', 'campus-pass-2026', 'test-token',
  ));
  expect(actions.verify).not.toHaveBeenCalled();
});

it('preserves intentional hyphens in pasted and typed login emails', () => {
  entrance();
  const identifier = screen.getByLabelText('Student Number or Email');

  fireEvent.change(identifier, { target: { value: '23-juan@example.com' } });
  expect(identifier).toHaveValue('23-juan@example.com');
  fireEvent.change(identifier, { target: { value: '20-01425@example.com' } });
  expect(identifier).toHaveValue('20-01425@example.com');

  fireEvent.change(identifier, { target: { value: '23' } });
  fireEvent.change(identifier, { target: { value: '23-' } });
  expect(identifier).toHaveValue('23-');
  fireEvent.change(identifier, { target: { value: '23-j' } });
  expect(identifier).toHaveValue('23-j');
});

it('removes the inserted separator when a typed student-number prefix becomes an email', () => {
  entrance();
  const identifier = screen.getByLabelText('Student Number or Email');

  fireEvent.change(identifier, { target: { value: '230' } });
  expect(identifier).toHaveValue('23-0');
  fireEvent.change(identifier, { target: { value: '23-0j' } });
  expect(identifier).toHaveValue('230j');
});

it('validates confirmation before student account creation and submits no role', async () => {
  entrance();
  fireEvent.click(screen.getAllByRole('link', { name: 'Create account' })[0]);
  expect(screen.getByRole('heading', { name: 'Create your account' })).toBeInTheDocument();
  expect(screen.getByLabelText('Email address')).toHaveFocus();
  expect(screen.getByRole('button', { name: 'Create account' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
  expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument();
  expect(screen.getByText('Meet all six password requirements before continuing.')).toBeInTheDocument();
  expect(screen.getByLabelText('Email address')).toHaveAttribute(
    'placeholder',
    'student@example.com',
  );
  fireEvent.change(screen.getByLabelText('Email address'), {
    target: { value: 'juan.delacruz@student.pnm.edu.ph' },
  });
  fireEvent.change(screen.getByLabelText('Password', { exact: true }), {
    target: { value: 'Synthetic-password-42!' },
  });
  expect(screen.getByRole('button', { name: 'Create account' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
  expect(screen.getByLabelText('Confirm password')).toBeRequired();
  expect(await screen.findByText('Meet all six password requirements before continuing.')).toBeInTheDocument();
  expect(screen.getByText('Enter the same password again.')).toBeInTheDocument();
  expect(actions.create).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('Confirm password'), {
    target: { value: 'Synthetic-password-42!' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
  await waitFor(() =>
    expect(actions.create).toHaveBeenCalledWith(
      'juan.delacruz@student.pnm.edu.ph',
      'Synthetic-password-42!',
    ),
  );
});

it('accepts and normalizes a personal email for student account creation', async () => {
  entrance();
  fireEvent.click(screen.getAllByRole('link', { name: 'Create account' })[0]);
  fireEvent.change(screen.getByLabelText('Email address'), {
    target: { value: ' Student.Demo@Gmail.com ' },
  });
  fireEvent.change(screen.getByLabelText('Password', { exact: true }), {
    target: { value: 'Synthetic-password-42!' },
  });
  fireEvent.change(screen.getByLabelText('Confirm password'), {
    target: { value: 'Synthetic-password-42!' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }));

  await waitFor(() => expect(actions.create).toHaveBeenCalledWith(
    'student.demo@gmail.com', 'Synthetic-password-42!',
  ));
});

it('offers Google sign-in and delegates identity verification to the server session', async () => {
  actions.google.mockResolvedValue({ user: { getIdToken: vi.fn().mockResolvedValue('id-token') } });
  actions.verifyGoogle.mockResolvedValue(undefined);
  entrance();
  completeHumanVerification();
  fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }));
  await waitFor(() => expect(actions.google).toHaveBeenCalledWith('test-token'));
  expect(actions.verify).not.toHaveBeenCalled();
  await waitFor(() => expect(actions.verifyGoogle).toHaveBeenCalledWith(
    expect.objectContaining({ getIdToken: expect.any(Function) }), 'test-token',
  ));
});

it('offers recovery without an enumeration-sensitive success message', async () => {
  entrance();
  fireEvent.click(screen.getAllByRole('link', { name: 'Forgot password?' })[0]);
  expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Email address'), {
    target: { value: 'student@synthetic.invalid' },
  });
  completeHumanVerification();
  fireEvent.click(screen.getByRole('button', { name: 'Send reset link' }));
  expect(await screen.findByText(/If your account can receive a reset link/)).toBeInTheDocument();
  expect(actions.recover).toHaveBeenCalledWith('student@synthetic.invalid', 'test-token');
});

it('does not store login Retry-After values in account-email cooldown buckets', async () => {
  actions.signIn.mockRejectedValueOnce(new RateLimitError('Please wait before trying again.', 42));
  entrance();
  fireEvent.change(screen.getByLabelText('Student Number or Email'), { target: { value: '23-01425' } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'campus-pass-2026' } });
  completeHumanVerification();
  fireEvent.click(screen.getByRole('button', { name: 'Sign in to ClassSync →' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Please wait before trying again.');
  expect(cooldownRemaining('verification-email', '23-01425')).toBe(0);
  expect(cooldownRemaining('password-reset', '23-01425')).toBe(0);
});

it('persists signup Retry-After without rendering a dead verification countdown', async () => {
  actions.create.mockRejectedValueOnce(new RateLimitError('Please wait before trying again.', 42));
  entrance();
  fireEvent.click(screen.getAllByRole('link', { name: 'Create account' })[0]);
  fireEvent.change(screen.getByLabelText('Email address'), { target: { value: ' Student.Demo@Example.com ' } });
  fireEvent.change(screen.getByLabelText('Password', { exact: true }), { target: { value: 'Synthetic-password-42!' } });
  fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'Synthetic-password-42!' } });
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Please wait before trying again.');
  expect(cooldownRemaining('verification-email', 'student.demo@example.com')).toBe(42);
  expect(screen.getByRole('button', { name: 'Create account' })).toBeEnabled();
  expect(screen.queryByRole('button', { name: /Resend in/ })).not.toBeInTheDocument();
});

it('normalizes recovery cooldowns and uses the server Retry-After duration', async () => {
  actions.recover.mockRejectedValueOnce(new RateLimitError('Please wait before requesting another email.', 27));
  entrance('/auth/forgot-password');
  fireEvent.change(screen.getByLabelText('Email address'), { target: { value: ' Student.Demo@Example.com ' } });
  completeHumanVerification();
  fireEvent.click(screen.getByRole('button', { name: 'Send reset link' }));
  expect(await screen.findByRole('button', { name: 'Resend in 27s' })).toBeDisabled();
  expect(cooldownRemaining('password-reset', 'student.demo@example.com')).toBe(27);
  expect(cooldownRemaining('verification-email', 'student.demo@example.com')).toBe(0);
});

it('recomputes the recovery countdown from its expiry after a background-tab delay', async () => {
  vi.useFakeTimers();
  const start = new Date('2026-11-21T00:00:00Z');
  vi.setSystemTime(start);
  startCooldown('password-reset', 'student@example.com', 30);
  entrance('/auth/forgot-password');
  fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'student@example.com' } });
  const resend = screen.getByRole('button', { name: 'Resend in 30s' });
  expect(resend).toBeDisabled();

  vi.setSystemTime(new Date(start.getTime() + 25_000));
  await act(async () => { vi.advanceTimersByTime(1000); });
  expect(screen.getByRole('button', { name: 'Resend in 4s' })).toBeDisabled();
});

it('keeps polling when a half-second tick still rounds to the same cooldown second', async () => {
  vi.useFakeTimers();
  const start = new Date('2026-11-21T00:00:00Z');
  vi.setSystemTime(start);
  startCooldown('password-reset', 'student@example.com', 2);
  entrance('/auth/forgot-password');
  fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'student@example.com' } });
  expect(screen.getByRole('button', { name: 'Resend in 2s' })).toBeDisabled();

  await act(async () => { vi.advanceTimersByTime(500); });
  expect(screen.getByRole('button', { name: 'Resend in 2s' })).toBeDisabled();
  await act(async () => { vi.advanceTimersByTime(500); });
  expect(screen.getByRole('button', { name: 'Resend in 1s' })).toBeDisabled();
  await act(async () => { vi.advanceTimersByTime(1000); });
  expect(screen.getByRole('button', { name: 'Send reset link' })).toBeEnabled();
});

it('surfaces a human-verification error instead of silently blocking valid credentials', async () => {
  entrance();
  fireEvent.change(screen.getByLabelText('Student Number or Email'), { target: { value: 'student@example.com' } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'Synthetic-password-42!' } });
  fireEvent.click(screen.getByRole('button', { name: 'Sign in to ClassSync →' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Complete the human verification check before continuing.');
  expect(actions.signIn).not.toHaveBeenCalled();
});

it('uses the same access card for password reset and requires all strength rules', async () => {
  actions.resetVerify.mockResolvedValue(undefined);
  entrance('/auth/reset-password?mode=resetPassword&oobCode=opaque-code');
  expect(await screen.findByRole('heading', { name: 'Create a new password' })).toBeInTheDocument();
  expect(await screen.findByText(/Password reset link is ready/i)).toBeInTheDocument();
  const submit = screen.getByRole('button', { name: 'Save new password' });
  expect(submit).toBeEnabled();
  fireEvent.click(submit);
  expect(await screen.findByText('Meet all six password requirements before continuing.')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'Campus-pass-26!' } });
  fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'Other-pass-26!' } });
  fireEvent.click(submit);
  expect(screen.getByText('Enter the same password again.')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'Campus-pass-26!' } });
  expect(submit).toBeEnabled();
  fireEvent.click(submit);
  await waitFor(() => expect(actions.resetComplete).toHaveBeenCalledWith('opaque-code', 'Campus-pass-26!'));
  expect(await screen.findByRole('status')).toHaveTextContent(/password has been changed/i);
});

it('routes an invitation through the universal sign-in', async () => {
  entrance('/auth/teacher-invite');
  expect(
    await screen.findByText(
      'Sign in with the account your university provided for this invitation.',
    ),
  ).toBeInTheDocument();
  expect(screen.queryByLabelText('Invitation code')).not.toBeInTheDocument();
});

it('uses the server-authorized workspace even when an external return target was supplied', async () => {
  entrance('/auth/login?returnTo=https%3A%2F%2Fexample.invalid%2Fstudent%2Fdashboard', {
    state: {
      status: 'authorized',
      membership: {
        role: 'student',
        student_id: 'synthetic',
        tenant_id: 't',
        uid: 'u',
        membership_revision: 1,
      },
    },
  });
  expect(await screen.findByRole('heading', { name: 'Student workspace' })).toBeInTheDocument();
});

it('shows the unavailable state without accepting credentials', () => {
  entrance('/', { available: false, state: { status: 'unavailable' } });
  expect(screen.getByText('Sign-in service unavailable. Reload to try again.')).toHaveAttribute(
    'role',
    'status',
  );
  expect(screen.getByLabelText('Student Number or Email')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Sign in to ClassSync →' })).toBeDisabled();
});
