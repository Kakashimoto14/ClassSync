import { lazy, Suspense, useCallback, useEffect, useRef, useState, type FocusEvent, type FormEvent, type ReactNode } from 'react';
import { AlertCircle, CircleAlert } from 'lucide-react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { ClassSyncLogo } from '../components/brand/ClassSyncLogo';
import { ClassSyncPageLoader } from '../components/loading/ClassSyncLoading';
import { Button } from '../components/ui/Button';
import { validateLogin, workspaceDestination, type LoginValidationErrors } from '../auth/access';
import {
  accountError,
  createStudentAccount,
  recoverPassword,
  signInWithGoogle,
  signInToAccount,
  verifyHumanChallenge,
  completePasswordReset,
  verifyPasswordResetCode,
  completeGoogleRedirectSignIn,
  verifyGoogleSignIn,
} from '../auth/account-actions';
import { identityEndpoint } from '../auth/university-session-driver';
import { TurnstileWidget } from '../auth/TurnstileWidget';
import type { TurnstileWidgetHandle } from '../auth/TurnstileWidget';
import { passwordStrengthComplete } from '../auth/password-strength';
import { formatLoginIdentifier, isValidAccountEmail, normalizeAccountEmail } from '../auth/student-number';
import { cooldownRemaining, retryAfterFrom, startCooldown } from '../auth/cooldown';
import { useUniversitySession } from '../auth/university-session-context';
import { UniversitySessionPanel } from '../auth/UniversitySessionPanel';
import { PasswordInput } from '../auth/PasswordInput';
import { devServer } from '../config/runtime-config';
import './institutional-entrance.css';

const AccountOnboardingPanel = lazy(() =>
  import('../auth/AccountOnboardingPanel').then((module) => ({ default: module.AccountOnboardingPanel })),
);
const AccountAdministrationPanel = lazy(() =>
  import('../auth/AccountAdministrationPanel').then((module) => ({ default: module.AccountAdministrationPanel })),
);

const EntranceShowcase = lazy(() =>
  import('./EntranceShowcase').then((module) => ({ default: module.EntranceShowcase })),
);

// Only sign-up and password reset show the checklist.
const PasswordStrengthChecklist = lazy(() =>
  import('../auth/PasswordStrengthChecklist').then((module) => ({ default: module.PasswordStrengthChecklist })),
);

const invitePath = '/auth/teacher-invite';
const verifyPath = '/auth/verify';
const onboardingPath = '/auth/student-onboarding';
const accountPath = '/auth/account';
const STUDENT_ID_PATTERN = /^[0-9]{2}-[0-9]{5}$/;

export function EntranceLayout({ children }: { children: ReactNode }) {
  const synthetic = devServer && import.meta.env.VITE_CLASSSYNC_SYNTHETIC_PREVIEW === 'true';
  return (
    <main className="connected-entrance">
      <div className="connected-entrance__frame">
        {/* The form comes first in the document; the grid places the showcase on the left. */}
        <section className="connected-entrance__access" aria-label="ClassSync account access">
          <header className="connected-entrance__header">
            <Link to="/" aria-label="ClassSync home">
              <ClassSyncLogo size="medium" decorative />
            </Link>
            {synthetic && (
              <p className="connected-entrance__preview">
                Local test environment &middot; Synthetic accounts only
              </p>
            )}
          </header>
          {children}
        </section>
        <Suspense fallback={<div className="entrance-showcase" aria-hidden="true" />}>
          <EntranceShowcase />
        </Suspense>
      </div>
    </main>
  );
}

export function InstitutionalEntrance() {
  const location = useLocation();
  const { state, available, refresh } = useUniversitySession();
  const path = location.pathname.replace(/\/+$/, '');
  const target = new URLSearchParams(location.search).get('returnTo');
  const invited = path === invitePath || target === invitePath;
  const search = target ? '?' + new URLSearchParams({ returnTo: target }) : '';
  const signedOut = state.status === 'signed-out';
  const mode = path === '/auth/signup'
    ? 'signup'
    : path === '/auth/forgot-password'
      ? 'recovery'
      : path === '/auth/reset-password'
        ? 'reset'
        : 'login';
  const resetCode = new URLSearchParams(location.search).get('oobCode') ?? '';
  const statusPage = [verifyPath, onboardingPath, invitePath, accountPath].includes(path);
  const statusHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    statusHeading.current?.focus();
  }, [path]);
  useEffect(() => {
    if (mode !== 'login' && mode !== 'recovery') return;
    const controller = new AbortController();
    void fetch(identityEndpoint('/health'), {
      method: 'GET', cache: 'no-store', credentials: 'omit', signal: controller.signal,
    }).catch(() => undefined);
    return () => controller.abort();
  }, [mode]);
  useEffect(() => {
    if (mode !== 'login') return;
    let active = true;
    void completeGoogleRedirectSignIn().then((result) => {
      if (result && active) refresh();
    });
    return () => { active = false; };
  }, [mode, refresh]);

  if (state.status === 'authorized' && path !== accountPath)
    return <Navigate replace to={workspaceDestination(state.membership.role, target)} />;
  if (signedOut && statusPage)
    return (
      <Navigate
        replace
        to={{
          pathname: '/auth/login',
          search: invited ? '?returnTo=%2Fauth%2Fteacher-invite' : search,
        }}
      />
    );
  if (state.status === 'verification-required' && path !== verifyPath)
    return (
      <Navigate
        replace
        to={{
          pathname: verifyPath,
          search: invited ? '?returnTo=%2Fauth%2Fteacher-invite' : search,
        }}
      />
    );
  if (state.status === 'denied' && path !== onboardingPath && path !== invitePath)
    return <Navigate replace to={{ pathname: invited ? invitePath : onboardingPath, search }} />;
  if (state.status === 'role-required' && path !== accountPath)
    return <Navigate replace to={{ pathname: accountPath, search }} />;

  const loginEntry = path === '/auth/login' || path === '';
  const canSignIn = (available && signedOut) || (loginEntry && mode === 'login');
  const formTitle =
    mode === 'signup'
      ? 'Create your account'
      : mode === 'recovery'
        ? 'Reset your password'
        : mode === 'reset'
          ? 'Create a new password'
          : 'Welcome to ClassSync';
  const title =
    path === verifyPath
      ? 'Verify your email'
      : path === onboardingPath
        ? 'Your student access'
        : path === invitePath
          ? 'Activate your invitation'
          : path === accountPath
            ? 'Your university account'
            : formTitle;

  return (
    <EntranceLayout>
      {canSignIn ? (
        // Deliberately unkeyed: switching between sign-in and sign-up keeps what was typed.
        <CredentialsForm
          mode={mode}
          title={formTitle}
          search={search}
          invited={invited}
          serviceAvailable={available}
          resetCode={resetCode}
        />
      ) : (
        <>
          <h1 ref={statusHeading} tabIndex={-1}>
            {title}
          </h1>
          {!available && state.status === 'checking' ? (
            <ClassSyncPageLoader label="Checking sign-in availability…" />
          ) : !available ? (
            <>
              <div className="entrance-availability" role="status">
                <CircleAlert size={17} aria-hidden="true" />
                <div>
                  <strong>University sign-in is unavailable</strong>
                  <p>Check your connection or try again in a moment.</p>
                </div>
              </div>
              <Button type="button" variant="secondary" onClick={() => refresh()}>
                Try again
              </Button>
              {mode !== 'login' && (
                <div className="connected-entrance__secondary">
                  <Link to="/auth/login">Back to sign in</Link>
                </div>
              )}
            </>
          ) : (
            <>
              <UniversitySessionPanel />
              <Suspense fallback={<ClassSyncPageLoader label="Opening account setup…" />}>
                {[verifyPath, onboardingPath, invitePath].includes(path) &&
                  state.status !== 'authorized' && (
                    <AccountOnboardingPanel entryRole={invited ? 'teacher' : 'student'} />
                  )}
                {path === accountPath &&
                  state.status === 'authorized' &&
                  state.membership.role === 'administrator' && (
                    <AccountAdministrationPanel
                      key={state.membership.uid}
                      uid={state.membership.uid}
                    />
                  )}
              </Suspense>
            </>
          )}
        </>
      )}
    </EntranceLayout>
  );
}

function CredentialsForm({
  mode,
  title,
  search,
  invited,
  resetCode,
  serviceAvailable = true,
}: {
  mode: 'login' | 'signup' | 'recovery' | 'reset';
  title: string;
  search: string;
  invited: boolean;
  resetCode: string;
  serviceAvailable?: boolean;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [errors, setErrors] = useState<LoginValidationErrors & { confirmation?: string }>({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const turnstileRef = useRef<TurnstileWidgetHandle>(null);
  const onTurnstileToken = useCallback((value: string) => setTurnstileToken(value), []);
  const heading = useRef<HTMLHeadingElement>(null);
  const emailField = useRef<HTMLInputElement>(null);
  const passwordField = useRef<HTMLInputElement>(null);
  const confirmationField = useRef<HTMLInputElement>(null);
  const signup = mode === 'signup';
  const recovery = mode === 'recovery';
  const resetting = mode === 'reset';
  const normalizedEmail = normalizeAccountEmail(email);
  const [resetCodeValid, setResetCodeValid] = useState(false);
  const [resetCodeChecking, setResetCodeChecking] = useState(resetting);
  const [cooldownSeconds, setCooldownSeconds] = useState(0);
  const session = useUniversitySession();
  const switchable = (mode === 'login' || signup) && !invited;

  const [shownMode, setShownMode] = useState(mode);
  if (shownMode !== mode) {
    // Typed values survive a mode change; feedback and one-use state do not.
    setShownMode(mode);
    setErrors({});
    setError('');
    setNotice('');
    setVisible(false);
    if (signup || resetting) setTurnstileToken('');
    if (resetting || shownMode === 'reset') {
      setPassword('');
      setConfirmation('');
    }
  }

  useEffect(() => {
    (mode === 'reset' ? passwordField : emailField).current?.focus();
  }, [mode]);

  useEffect(() => {
    setCooldownSeconds(recovery ? cooldownRemaining('password-reset', normalizedEmail) : 0);
  }, [normalizedEmail, recovery]);

  const hasRecoveryCooldown = recovery && cooldownSeconds > 0;
  useEffect(() => {
    if (!hasRecoveryCooldown) return;
    const timer = window.setInterval(() => {
      setCooldownSeconds(cooldownRemaining('password-reset', normalizedEmail));
    }, 500);
    return () => window.clearInterval(timer);
  }, [hasRecoveryCooldown, normalizedEmail]);

  useEffect(() => {
    if (!busy) {
      setConnecting(false);
      return;
    }
    const timer = window.setTimeout(() => setConnecting(true), 4_000);
    return () => window.clearTimeout(timer);
  }, [busy]);

  useEffect(() => {
    if (!resetting) return;
    let active = true;
    if (!resetCode) {
      setResetCodeValid(false);
      setResetCodeChecking(false);
      setError('This password reset link is invalid or expired. Request a new one.');
      return () => { active = false; };
    }
    setResetCodeChecking(true);
    void verifyPasswordResetCode(resetCode).then(
      () => {
        if (active) {
          setResetCodeValid(true);
          setNotice('Password reset link is ready. Choose a new password below.');
        }
      },
      () => {
        if (active) setError('This password reset link is invalid or expired. Request a new one.');
      },
    ).finally(() => { if (active) setResetCodeChecking(false); });
    return () => { active = false; };
  }, [resetCode, resetting]);

  function emailProblem(): string | undefined {
    if (signup || recovery)
      return isValidAccountEmail(email) ? undefined : 'Enter a valid email address.';
    if (STUDENT_ID_PATTERN.test(email.trim())) return undefined;
    return validateLogin(normalizedEmail, 'unchecked').email;
  }

  // Check a filled field as the person leaves it. Skip when they are heading to a button
  // or link, so a new message never moves the thing they are about to press.
  function validateOnBlur(event: FocusEvent, field: 'email' | 'confirmation') {
    const next = event.relatedTarget;
    if (next instanceof HTMLButtonElement || next instanceof HTMLAnchorElement) return;
    if (field === 'email' && email.trim())
      setErrors((current) => ({ ...current, email: emailProblem() }));
    if (field === 'confirmation' && confirmation)
      setErrors((current) => ({
        ...current,
        confirmation: confirmation === password ? undefined : 'Enter the same password again.',
      }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const studentNumberLogin = mode === 'login' && STUDENT_ID_PATTERN.test(email.trim());
    const validation: typeof errors = (studentNumberLogin || resetting)
      ? {}
      : validateLogin(normalizedEmail, password);
    if (studentNumberLogin && !password) validation.password = 'Enter your password.';
    if (recovery) delete validation.password;
    if ((signup || recovery) && !isValidAccountEmail(email))
      validation.email = 'Enter a valid email address.';
    if ((signup || resetting) && !passwordStrengthComplete(password, confirmation))
      validation.password = 'Meet all six password requirements before continuing.';
    if ((signup || resetting) && confirmation !== password)
      validation.confirmation = 'Enter the same password again.';
    setErrors(validation);
    setError('');
    setNotice('');
    if (validation.email) return emailField.current?.focus();
    if (validation.password) return passwordField.current?.focus();
    if (validation.confirmation) return confirmationField.current?.focus();
    if ((mode === 'login' || recovery) && !turnstileToken) {
      setError('Complete the human verification check before continuing.');
      return;
    }
    setBusy(true);
    try {
      if (resetting) {
        await completePasswordReset(resetCode, password);
        setPassword('');
        setConfirmation('');
        setNotice('Your password has been changed. You can now sign in.');
      } else if (recovery) {
        await recoverPassword(normalizedEmail, turnstileToken);
        setCooldownSeconds(startCooldown('password-reset', normalizedEmail, 30));
        setNotice('If your account can receive a reset link, check your email for the next steps.');
      } else if (signup) {
        await createStudentAccount(normalizedEmail, password);
        startCooldown('verification-email', normalizedEmail, 30);
      }
      else {
        if (studentNumberLogin) {
          await signInToAccount(email.trim(), password, turnstileToken);
        } else {
          await verifyHumanChallenge(turnstileToken);
          await signInToAccount(normalizedEmail, password);
        }
        session.refresh();
      }
    } catch (failure) {
      const retryAfter = retryAfterFrom(failure);
      if (retryAfter && recovery) {
        setCooldownSeconds(startCooldown('password-reset', normalizedEmail, retryAfter));
      } else if (retryAfter && signup) {
        startCooldown('verification-email', normalizedEmail, retryAfter);
      }
      setError(
        failure instanceof Error && failure.name === 'RateLimitError'
          ? failure.message
          : resetting
          ? 'The password could not be changed. Request a new reset link and try again.'
          : mode === 'login' && studentNumberLogin
          ? 'Invalid student number or password.'
          : mode === 'login'
            ? 'We could not sign you in. Check your email and password, or try resetting your password.'
          : recovery
            ? 'We could not reach the reset service. Please try again in a moment.'
          : accountError(failure),
      );
      if ((mode === 'login' || recovery) && turnstileToken) {
        setTurnstileToken('');
        turnstileRef.current?.reset();
      }
    } finally {
      setBusy(false);
    }
  }

  async function continueWithGoogle() {
    if (busy) return;
    if (!turnstileToken) {
      setError('Complete the human verification check first.');
      return;
    }
    setBusy(true);
    setError('');
    setNotice('');
    try {
      // Call Firebase synchronously from this gesture before any network await.
      const popupPromise = signInWithGoogle(turnstileToken);
      const result = await popupPromise;
      if (result?.user) {
        await verifyGoogleSignIn(result.user, turnstileToken);
        session.refresh();
      }
    } catch (failure) {
      await Promise.resolve(session.signOut()).catch(() => undefined);
      setError(accountError(failure));
      if (turnstileToken) {
        setTurnstileToken('');
        turnstileRef.current?.reset();
      }
    } finally {
      setBusy(false);
    }
  }

  const holdWhileBusy = (event: { preventDefault: () => void }) => {
    if (busy) event.preventDefault();
  };

  return (
    <>
      {mode === 'login' && <p className="connected-entrance__eyebrow">CAMPUS ACCESS</p>}
      <h1 ref={heading} tabIndex={-1}>
        {title}
      </h1>
      <p className="connected-entrance__intro">
        {recovery
          ? 'Enter your email to request a reset link.'
          : signup
            ? 'Create your account with an email you can access, then verify it.'
            : invited
              ? 'Sign in with the account your university provided for this invitation.'
              : resetting
                ? 'Choose a password you have not used before.'
                : 'Use your student number, email, or Google account.'}
      </p>
      {switchable && (
        <nav className="auth-switch" aria-label="Sign in or create an account">
          <Link
            to={{ pathname: '/auth/login', search }}
            aria-current={mode === 'login' ? 'page' : undefined}
            aria-disabled={busy || undefined}
            onClick={holdWhileBusy}
          >
            Sign in
          </Link>
          <Link
            to={{ pathname: '/auth/signup', search }}
            aria-current={signup ? 'page' : undefined}
            aria-disabled={busy || undefined}
            onClick={holdWhileBusy}
          >
            Create account
          </Link>
        </nav>
      )}
      <form className="connected-entrance__form" noValidate onSubmit={submit} aria-busy={busy}>
        {!resetting && <div className="auth-field">
          <label htmlFor="entrance-email">
            {mode === 'login' ? 'Student Number or Email' : 'Email address'}
          </label>
          <input
            id="entrance-email"
            ref={emailField}
            type={mode === 'login' ? 'text' : 'email'}
            placeholder={mode === 'login'
              ? '23-01425 or student@example.com'
              : 'student@example.com'}
            autoComplete="username"
            inputMode={mode === 'login' ? 'text' : 'email'}
            autoCapitalize="none"
            spellCheck={false}
            required
            disabled={busy}
            value={email}
            aria-invalid={!!errors.email}
            aria-describedby={errors.email ? 'entrance-email-error' : undefined}
            onBlur={(event) => validateOnBlur(event, 'email')}
            onChange={(event) => {
              setEmail(mode === 'login'
                ? formatLoginIdentifier(event.target.value, email)
                : event.target.value);
              setErrors({ ...errors, email: undefined });
            }}
          />
          {errors.email && (
            <p id="entrance-email-error" className="entrance-error">
              {errors.email}
            </p>
          )}
        </div>}
        {!recovery && (
          <div className="auth-field">
            <div className="connected-entrance__password-label-row">
              <label htmlFor="entrance-password">{resetting ? 'New password' : 'Password'}</label>
              {mode === 'login' && (
                <Link className="connected-entrance__recovery" to={{ pathname: '/auth/forgot-password', search }}>
                  Forgot password?
                </Link>
              )}
            </div>
            <PasswordInput
              id="entrance-password"
              ref={passwordField}
              visible={visible}
              onToggle={() => setVisible(!visible)}
              autoComplete={signup || resetting ? 'new-password' : 'current-password'}
              minLength={signup || resetting ? 12 : undefined}
              maxLength={signup || resetting ? 128 : undefined}
              required
              disabled={busy}
              value={password}
              aria-invalid={!!errors.password}
              aria-describedby={
                [(signup || resetting) && 'entrance-password-hint', errors.password && 'entrance-password-error']
                  .filter(Boolean)
                  .join(' ') || undefined
              }
              onChange={(event) => {
                setPassword(event.target.value);
                setErrors({ ...errors, password: undefined });
              }}
            />
            {(signup || resetting) && (
              <p id="entrance-password-hint" className="entrance-hint">
                Use the checklist to create a strong password.
              </p>
            )}
            {errors.password && (
              <p id="entrance-password-error" className="entrance-error">
                {errors.password}
              </p>
            )}
          </div>
        )}
        {(signup || resetting) && (
          <div className="auth-field">
            <label htmlFor="entrance-confirm">Confirm password</label>
            <PasswordInput
              id="entrance-confirm"
              ref={confirmationField}
              visible={visible}
              onBlur={(event) => validateOnBlur(event, 'confirmation')}
              autoComplete="new-password"
              minLength={12}
              maxLength={128}
              required
              disabled={busy}
              value={confirmation}
              aria-invalid={!!errors.confirmation}
              aria-describedby={errors.confirmation ? 'entrance-confirm-error' : undefined}
              onChange={(event) => {
                setConfirmation(event.target.value);
                setErrors({ ...errors, confirmation: undefined });
              }}
            />
            {errors.confirmation && (
              <p id="entrance-confirm-error" className="entrance-error">
                {errors.confirmation}
              </p>
            )}
          </div>
        )}
        {(signup || resetting) && (
          <Suspense fallback={null}>
            <PasswordStrengthChecklist password={password} confirmPassword={confirmation} />
          </Suspense>
        )}
        {resetting && resetCodeChecking && <p role="status">Checking your password reset link…</p>}
        {(mode === 'login' || recovery) && <TurnstileWidget ref={turnstileRef} onToken={onTurnstileToken} />}
        {connecting && busy && (
          <p className="connected-entrance__connecting" role="status">
            Connecting to ClassSync server…
          </p>
        )}
        {error && (
          <div className="connected-entrance__alert" role="alert">
            <AlertCircle size={17} aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}
        {notice && (
          <p className="entrance-notice" role="status">
            {notice}
          </p>
        )}
        <Button type="submit" loading={busy} disabled={busy || !serviceAvailable ||
          (recovery && cooldownSeconds > 0) ||
          (resetting && (resetCodeChecking || !resetCodeValid))}>
          {busy
            ? 'Please wait…'
            : signup
              ? 'Create account'
              : recovery
                ? cooldownSeconds > 0 ? `Resend in ${cooldownSeconds}s` : 'Send reset link'
                : resetting
                  ? 'Save new password'
                : 'Sign in to ClassSync →'}
        </Button>
      </form>
      {mode === 'login' && !invited && (
        <div className="connected-entrance__first-time">
          <span className="connected-entrance__divider">or</span>
          <Button type="button" variant="secondary" disabled={busy || !serviceAvailable} onClick={continueWithGoogle}>
            <GoogleMark />
            Continue with Google
          </Button>
          <aside className="connected-entrance__callout">
            <strong>Signing in for the first time?</strong>
            <p>Use a Google account you can access, verify your email, then set a password.</p>
          </aside>
          <p
            className="connected-entrance__help"
            role={serviceAvailable ? undefined : 'status'}
          >
            {serviceAvailable
              ? 'Need help signing in? Visit the Office of the Registrar.'
              : 'Sign-in service unavailable. Reload to try again.'}
          </p>
        </div>
      )}
      {(mode === 'recovery' || mode === 'reset' || invited) && (
        <div className="connected-entrance__secondary">
          {mode === 'login' ? (
            <Link to="/auth/login">Back to regular sign in</Link>
          ) : (
            <Link to={{ pathname: '/auth/login', search }}>Back to sign in</Link>
          )}
        </div>
      )}
    </>
  );
}

function GoogleMark() {
  return (
    <svg className="google-mark" width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#4285F4" d="M43.6 24.5c0-1.4-.1-2.8-.4-4.1H24v7.8h11a9.4 9.4 0 0 1-4.1 6.2v5.1h6.7c3.9-3.6 6-8.8 6-15Z" />
      <path fill="#34A853" d="M24 44c5.5 0 10.1-1.8 13.5-4.8l-6.7-5.1c-1.8 1.2-4 1.9-6.8 1.9-5.2 0-9.6-3.5-11.2-8.2H5.9v5.2A20 20 0 0 0 24 44Z" />
      <path fill="#FBBC05" d="M12.8 27.8a12 12 0 0 1 0-7.6V15H5.9a20 20 0 0 0 0 18l6.9-5.2Z" />
      <path fill="#EA4335" d="M24 12c3 0 5.7 1 7.8 3.1l5.9-5.9C34.1 5.9 29.5 4 24 4A20 20 0 0 0 5.9 15l6.9 5.2C14.4 15.5 18.8 12 24 12Z" />
    </svg>
  );
}
