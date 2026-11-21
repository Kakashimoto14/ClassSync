import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { InstitutionalEntrance } from './InstitutionalEntrance';
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

beforeEach(() => vi.clearAllMocks());

it('shows the CdM campus access login and a non-production verification widget', async () => {
  entrance();
  expect(screen.getByRole('heading', { name: 'Welcome to ClassSync' })).toBeInTheDocument();
  expect(screen.getByText('CAMPUS ACCESS')).toBeInTheDocument();
  expect(screen.getAllByText('Signing in for the first time?')).toHaveLength(2);
  expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeInTheDocument();
  expect(await screen.findByText(/test verification ready/i)).toBeInTheDocument();
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
  expect(screen.getByRole('button', { name: 'Sign in to ClassSync →' })).toBeDisabled();
  expect(screen.getByLabelText('Student Number or Email')).toBeRequired();
  fireEvent.change(screen.getByLabelText('Student Number or Email'), {
    target: { value: 'student@synthetic.invalid' },
  });
  fireEvent.change(screen.getByLabelText('Password'), {
    target: { value: 'Synthetic-password-42!' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
  expect(screen.getByRole('button', { name: 'Show password' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  fireEvent.click(screen.getByRole('button', { name: 'Sign in to ClassSync →' }));
  await waitFor(() =>
    expect(actions.signIn).toHaveBeenCalledWith(
      'student@synthetic.invalid',
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
  fireEvent.click(screen.getByRole('button', { name: 'Sign in to ClassSync →' }));

  await waitFor(() => expect(actions.signIn).toHaveBeenCalledWith(
    '23-01425', 'campus-pass-2026', 'test-token',
  ));
  expect(actions.verify).not.toHaveBeenCalled();
});

it('validates confirmation before student account creation and submits no role', async () => {
  entrance();
  fireEvent.click(screen.getAllByRole('link', { name: 'Create account' })[0]);
  expect(screen.getByRole('heading', { name: 'Create your account' })).toHaveFocus();
  expect(screen.getByLabelText('Email address')).toHaveAttribute(
    'placeholder',
    'student.demo@gmail.com',
  );
  fireEvent.change(screen.getByLabelText('Email address'), {
    target: { value: 'juan.delacruz@student.pnm.edu.ph' },
  });
  fireEvent.change(screen.getByLabelText('Password', { exact: true }), {
    target: { value: 'Synthetic-password-42!' },
  });
  expect(screen.getByRole('button', { name: 'Create account' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Create account' }));
  expect(screen.getByLabelText('Confirm password')).toBeRequired();
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
  await screen.findByText(/test verification ready/i);
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
  fireEvent.click(screen.getByRole('button', { name: 'Send reset link' }));
  expect(await screen.findByText(/If your account can receive a reset link/)).toBeInTheDocument();
  expect(actions.recover).toHaveBeenCalledWith('student@synthetic.invalid', 'test-token');
});

it('uses the same access card for password reset and requires all strength rules', async () => {
  actions.resetVerify.mockResolvedValue(undefined);
  entrance('/auth/reset-password?mode=resetPassword&oobCode=opaque-code');
  expect(await screen.findByRole('heading', { name: 'Create a new password' })).toBeInTheDocument();
  expect(await screen.findByText(/Password reset link is ready/i)).toBeInTheDocument();
  const submit = screen.getByRole('button', { name: 'Save new password' });
  expect(submit).toBeDisabled();
  fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'Campus-pass-26!' } });
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
