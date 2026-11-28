import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useEffect } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { InstitutionalEntrance } from './InstitutionalEntrance';
import { EmailActionPage } from './EmailActionPage';
import { AccountOnboardingPanel } from '../auth/AccountOnboardingPanel';
import { UniversitySessionContext } from '../auth/university-session-context';

const actions = vi.hoisted(() => ({
  create: vi.fn(), signIn: vi.fn(), verify: vi.fn(), request: vi.fn(), refreshAccount: vi.fn(),
  resend: vi.fn(), resetVerify: vi.fn(), resetComplete: vi.fn(),
}));
vi.mock('../auth/account-actions', async (original) => ({
  ...(await original<typeof import('../auth/account-actions')>()),
  createStudentAccount: actions.create,
  signInToAccount: actions.signIn,
  verifyHumanChallenge: actions.verify,
  accountRequest: actions.request,
  refreshVerifiedAccount: actions.refreshAccount,
  resendVerification: actions.resend,
  verifyPasswordResetCode: actions.resetVerify,
  completePasswordReset: actions.resetComplete,
  completeGoogleRedirectSignIn: vi.fn().mockResolvedValue(null),
  observeAccountProfile: vi.fn(async (next: (profile: unknown) => void) => {
    next({ uid: 'u1', name: '', email: 'juan@example.com', emailVerified: false });
    return vi.fn();
  }),
}));
vi.mock('../auth/TurnstileWidget', async () => {
  const React = await import('react');
  return {
    TurnstileWidget: React.forwardRef<{ reset: () => void }, { onToken: (token: string) => void }>(
      function TestTurnstile({ onToken }, ref) {
        React.useImperativeHandle(ref, () => ({ reset: () => onToken('') }), [onToken]);
        useEffect(() => onToken('test-token'), [onToken]);
        return null;
      },
    ),
  };
});

const session = { available: true, refresh: vi.fn(), signOut: vi.fn() };

// Separate route entries, as in the real router, so a remount would be caught.
function entrance(path = '/auth/login') {
  render(
    <UniversitySessionContext.Provider value={{ ...session, state: { status: 'signed-out' } }}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/auth/login" element={<InstitutionalEntrance />} />
          <Route path="/auth/signup" element={<InstitutionalEntrance />} />
          <Route path="/auth/forgot-password" element={<InstitutionalEntrance />} />
        </Routes>
      </MemoryRouter>
    </UniversitySessionContext.Provider>,
  );
}
const modeSwitch = (name: string) => screen.getByRole('link', { name });
const type = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
});

describe('sign in / create account switcher', () => {
  it('keeps typed values across modes and marks the current one', () => {
    entrance();
    expect(modeSwitch('Sign in')).toHaveAttribute('aria-current', 'page');
    type('Student Number or Email', 'juan@example.com');
    type('Password', 'Typed-password-42!');
    fireEvent.click(modeSwitch('Create account'));
    expect(modeSwitch('Create account')).toHaveAttribute('aria-current', 'page');
    expect(screen.getByLabelText('Email address')).toHaveValue('juan@example.com');
    expect(screen.getByLabelText('Password')).toHaveValue('Typed-password-42!');
    type('Confirm password', 'Typed-password-42!');
    fireEvent.click(modeSwitch('Sign in'));
    expect(screen.getByLabelText('Student Number or Email')).toHaveValue('juan@example.com');
    fireEvent.click(screen.getByRole('link', { name: 'Forgot password?' }));
    expect(screen.getByLabelText('Email address')).toHaveValue('juan@example.com');
  });

  it('focuses the first field on arrival and after each mode change', () => {
    entrance();
    expect(screen.getByLabelText('Student Number or Email')).toHaveFocus();
    fireEvent.click(modeSwitch('Create account'));
    expect(screen.getByLabelText('Email address')).toHaveFocus();
  });

  it('clears stale feedback when the mode changes', async () => {
    entrance();
    fireEvent.click(screen.getByRole('button', { name: 'Sign in to ClassSync →' }));
    expect(await screen.findByText('Enter your password.')).toBeInTheDocument();
    fireEvent.click(modeSwitch('Create account'));
    expect(screen.queryByText('Enter your password.')).not.toBeInTheDocument();
  });

  it('toggles password visibility for both sign-up fields', () => {
    entrance('/auth/signup');
    const toggle = screen.getByRole('button', { name: 'Show password' });
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'text');
    expect(screen.getByLabelText('Confirm password')).toHaveAttribute('type', 'text');
    fireEvent.click(toggle);
    expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'password');
  });

  it('submits through the form default button, as Enter does', async () => {
    actions.signIn.mockResolvedValue(undefined);
    entrance();
    type('Student Number or Email', 'juan@example.com');
    type('Password', 'Typed-password-42!');
    const form = screen.getByLabelText('Password').closest('form')!;
    // Implicit submission activates the first submit button, so it must not be the eye toggle.
    expect(form.querySelector('button:not([type="button"])')).toHaveTextContent('Sign in to ClassSync');
    form.requestSubmit();
    await waitFor(() => expect(actions.signIn).toHaveBeenCalledWith('juan@example.com', 'Typed-password-42!'));
  });

  it('validates a filled email when it loses focus, not an empty one', () => {
    entrance('/auth/signup');
    const email = screen.getByLabelText('Email address');
    fireEvent.blur(email);
    expect(screen.queryByText('Enter a valid email address.')).not.toBeInTheDocument();
    type('Email address', 'juan@');
    fireEvent.blur(email);
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();
    expect(email).toHaveAttribute('aria-invalid', 'true');
  });

  it.each([
    ['/auth/login', 'Sign in to ClassSync →', /We could not sign you in/],
    ['/auth/signup', 'Create account', /could not be confirmed/],
  ])('shows mapped copy instead of provider errors on %s', async (path, button, copy) => {
    const raw = new Error('FirebaseError: INTERNAL socket 10.0.0.1 closed');
    actions.signIn.mockRejectedValue(raw);
    actions.create.mockRejectedValue(raw);
    entrance(path);
    type(path === '/auth/login' ? 'Student Number or Email' : 'Email address', 'juan@example.com');
    type('Password', 'Typed-password-42!');
    if (path === '/auth/signup') type('Confirm password', 'Typed-password-42!');
    fireEvent.click(screen.getByRole('button', { name: button }));
    expect(await screen.findByRole('alert')).toHaveTextContent(copy);
    expect(screen.queryByText(/FirebaseError|10\.0\.0\.1/)).not.toBeInTheDocument();
  });
});

describe('verification and onboarding', () => {
  const onboarding = () =>
    render(
      <MemoryRouter>
        <UniversitySessionContext.Provider
          value={{ ...session, state: { status: 'verification-required' } }}
        >
          <AccountOnboardingPanel />
        </UniversitySessionContext.Provider>
      </MemoryRouter>,
    );
  const status = (verified: boolean) => ({
    email_verified: verified, claim_state: null, membership_state: null,
    status: 'unlinked', verification_mode: 'cor_or_roster',
  });

  it('starts a resend cooldown, then continues to a prefilled, locked claim email', async () => {
    let verified = false;
    actions.request.mockImplementation(async () => status(verified));
    actions.resend.mockResolvedValue(undefined);
    onboarding();

    const next = await screen.findByRole('button', { name: 'I’ve verified — Continue' });
    expect(screen.getByText('Email')).toHaveAttribute('aria-current', 'step');
    fireEvent.click(screen.getByRole('button', { name: 'Resend verification email' }));
    expect(await screen.findByRole('button', { name: /Resend verification email in \d+s/ })).toBeDisabled();

    await waitFor(() => expect(next).toBeEnabled());
    fireEvent.click(next);
    expect(await screen.findByText(/Your email is not verified yet/)).toBeInTheDocument();

    verified = true;
    await waitFor(() => expect(next).toBeEnabled());
    fireEvent.click(next);
    const claim = await screen.findByLabelText('Email address');
    expect(claim).toHaveValue('juan@example.com');
    expect(claim).toHaveAttribute('readonly');
    expect(actions.refreshAccount).toHaveBeenCalledWith('u1');
    expect(screen.getByText('Student record')).toHaveAttribute('aria-current', 'step');
  });

  it('maps a network failure to connection guidance', async () => {
    actions.request.mockResolvedValue(status(false));
    actions.resend.mockRejectedValue(new TypeError('Failed to fetch'));
    onboarding();
    fireEvent.click(await screen.findByRole('button', { name: 'Resend verification email' }));
    expect(await screen.findByText(/Check your connection and try again/)).toBeInTheDocument();
    expect(screen.queryByText('Failed to fetch')).not.toBeInTheDocument();
  });

  it('never shows a raw error from an email reset link', async () => {
    actions.resetVerify.mockResolvedValue(undefined);
    actions.resetComplete.mockRejectedValue(new Error('sql: relation missing'));
    render(
      <UniversitySessionContext.Provider value={{ ...session, state: { status: 'signed-out' } }}>
        <MemoryRouter initialEntries={['/auth/action?mode=resetPassword&oobCode=code']}>
          <EmailActionPage />
        </MemoryRouter>
      </UniversitySessionContext.Provider>,
    );
    const password = await screen.findByLabelText('New password');
    expect(password).toHaveFocus();
    type('New password', 'Campus-pass-26!');
    type('Confirm password', 'Campus-pass-26!');
    fireEvent.click(screen.getByRole('button', { name: 'Save new password' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('The password could not be changed.');
    expect(screen.queryByText(/sql:/)).not.toBeInTheDocument();
  });
});
