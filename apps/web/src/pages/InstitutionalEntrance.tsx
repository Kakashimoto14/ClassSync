import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { CalendarDays, CircleAlert, DoorOpen, Eye, EyeOff, ShieldCheck } from 'lucide-react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { ClassSyncLogo } from '../components/brand/ClassSyncLogo';
import { Button } from '../components/ui/Button';
import { validateLogin, workspaceDestination, type LoginValidationErrors } from '../auth/access';
import {
  accountError,
  createStudentAccount,
  recoverPassword,
  signInWithGoogle,
  signInToAccount,
  verifyHumanChallenge,
} from '../auth/account-actions';
import { TurnstileWidget } from '../auth/TurnstileWidget';
import { useUniversitySession } from '../auth/university-session-context';
import { UniversitySessionPanel } from '../auth/UniversitySessionPanel';
import { AccountOnboardingPanel } from '../auth/AccountOnboardingPanel';
import { AccountAdministrationPanel } from '../auth/AccountAdministrationPanel';
import { devServer } from '../config/runtime-config';
import './institutional-entrance.css';

const invitePath = '/auth/teacher-invite';
const verifyPath = '/auth/verify';
const onboardingPath = '/auth/student-onboarding';
const accountPath = '/auth/account';
const STUDENT_EMAIL_PATTERN = /^[a-z]+(?:\.[a-z]+)*@student\.pnm\.edu\.ph$/;

function ProductPreview() {
  return (
    <aside className="connected-entrance__story" aria-label="ClassSync campus services">
      <div className="connected-entrance__portal-brand">
        <ClassSyncLogo size="medium" decorative />
        <span>COLEGIO DE MONTALBAN · CLASSSYNC PORTAL</span>
      </div>
      <h2>
        Smarter schedules.<br />Better campus days<span>.</span>
      </h2>
      <p>Academic and scheduling services for the Colegio de Montalban community.</p>
      <ul className="connected-entrance__features">
        <li><CalendarDays size={19} aria-hidden="true" />View class schedules and room assignments</li>
        <li><DoorOpen size={19} aria-hidden="true" />Check building and laboratory availability</li>
        <li><ShieldCheck size={19} aria-hidden="true" />Stay informed about official schedule updates</li>
      </ul>
      <small className="connected-entrance__service-label">ACADEMIC &amp; SCHEDULING SERVICES</small>
    </aside>
  );
}

export function EntranceLayout({ children }: { children: ReactNode }) {
  const synthetic = devServer && import.meta.env.VITE_CLASSSYNC_SYNTHETIC_PREVIEW === 'true';
  return (
    <main className="connected-entrance">
      <div className="connected-entrance__frame">
        <section className="connected-entrance__access" aria-label="ClassSync account access">
          <header className="connected-entrance__header">
            <Link to="/" aria-label="ClassSync home">
              <ClassSyncLogo size="large" decorative />
            </Link>
            {synthetic && (
              <p className="connected-entrance__preview">
                Local test environment &middot; Synthetic accounts only
              </p>
            )}
          </header>
          {children}
        </section>
        <ProductPreview />
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
  const mode =
    path === '/auth/signup' ? 'signup' : path === '/auth/forgot-password' ? 'recovery' : 'login';
  const statusPage = [verifyPath, onboardingPath, invitePath, accountPath].includes(path);
  const statusHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    statusHeading.current?.focus();
  }, [path]);

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

  const canSignIn = available && signedOut;
  const formTitle =
    mode === 'signup'
      ? 'Create your account'
      : mode === 'recovery'
        ? 'Reset your password'
    : 'Welcome, CdMian!';
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
        <CredentialsForm
          key={mode}
          mode={mode}
          title={formTitle}
          search={search}
          invited={invited}
        />
      ) : (
        <>
          <h1 ref={statusHeading} tabIndex={-1}>
            {title}
          </h1>
          {!available && state.status === 'checking' ? (
            <p role="status">Checking sign-in availability…</p>
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
}: {
  mode: 'login' | 'signup' | 'recovery';
  title: string;
  search: string;
  invited: boolean;
}) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<LoginValidationErrors & { confirmation?: string }>({});
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const [turnstileRevision, setTurnstileRevision] = useState(0);
  const onTurnstileToken = useCallback((value: string) => setTurnstileToken(value), []);
  const heading = useRef<HTMLHeadingElement>(null);
  const emailField = useRef<HTMLInputElement>(null);
  const passwordField = useRef<HTMLInputElement>(null);
  const confirmationField = useRef<HTMLInputElement>(null);
  const signup = mode === 'signup';
  const recovery = mode === 'recovery';

  useEffect(() => {
    heading.current?.focus();
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const validation: typeof errors = validateLogin(email.trim(), password);
    if (recovery) delete validation.password;
    if (signup && !STUDENT_EMAIL_PATTERN.test(email.trim()))
      validation.email = 'Use a lowercase institutional email such as juan.delacruz@student.pnm.edu.ph.';
    if (signup && password.length < 12) validation.password = 'Use at least 12 characters.';
    if (signup && confirmation !== password)
      validation.confirmation = 'Enter the same password again.';
    setErrors(validation);
    setError('');
    setNotice('');
    if (validation.email) return emailField.current?.focus();
    if (validation.password) return passwordField.current?.focus();
    if (validation.confirmation) return confirmationField.current?.focus();
    setBusy(true);
    try {
      if (recovery) {
        await recoverPassword(email);
        setNotice('If your account can receive a reset link, check your email for the next steps.');
      } else if (signup) await createStudentAccount(email, password);
      else {
        await verifyHumanChallenge(turnstileToken);
        await signInToAccount(email, password);
      }
    } catch (failure) {
      setError(
        mode === 'login'
          ? 'We could not sign you in. Check your email and password, or try resetting your password.'
          : accountError(failure),
      );
    } finally {
      if (mode === 'login' && turnstileToken) {
        setTurnstileToken('');
        setTurnstileRevision((revision) => revision + 1);
      }
      setBusy(false);
    }
  }

  async function continueWithGoogle() {
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await verifyHumanChallenge(turnstileToken);
      await signInWithGoogle();
    } catch (failure) {
      setError(accountError(failure));
    } finally {
      if (turnstileToken) {
        setTurnstileToken('');
        setTurnstileRevision((revision) => revision + 1);
      }
      setBusy(false);
    }
  }

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
            ? 'Create your account with the email on your student record, then verify it.'
            : invited
              ? 'Sign in with the account your university provided for this invitation.'
              : 'Sign in to stay connected to your campus schedule and rooms.'}
      </p>
      <form className="connected-entrance__form" noValidate onSubmit={submit} aria-busy={busy}>
        <div className="auth-field">
          <label htmlFor="entrance-email">{mode === 'login' ? 'Institutional email' : 'Email'}</label>
          <input
            id="entrance-email"
            ref={emailField}
            type="email"
            placeholder={mode === 'login' || signup ? 'juan.delacruz@student.pnm.edu.ph' : undefined}
            autoComplete="username"
            inputMode="email"
            autoCapitalize="none"
            spellCheck={false}
            required
            disabled={busy}
            value={email}
            aria-invalid={!!errors.email}
            aria-describedby={errors.email ? 'entrance-email-error' : undefined}
            onChange={(event) => {
              setEmail(event.target.value);
              setErrors({ ...errors, email: undefined });
            }}
          />
          {errors.email && (
            <p id="entrance-email-error" className="entrance-error">
              {errors.email}
            </p>
          )}
        </div>
        {!recovery && (
          <div className="auth-field">
            <label htmlFor="entrance-password">Password</label>
            <div className="entrance-password">
              <input
                id="entrance-password"
                ref={passwordField}
                type={visible ? 'text' : 'password'}
                autoComplete={signup ? 'new-password' : 'current-password'}
                required
                disabled={busy}
                value={password}
                aria-invalid={!!errors.password}
                aria-describedby={
                  [signup && 'entrance-password-hint', errors.password && 'entrance-password-error']
                    .filter(Boolean)
                    .join(' ') || undefined
                }
                onChange={(event) => {
                  setPassword(event.target.value);
                  setErrors({ ...errors, password: undefined });
                }}
              />
              <button
                type="button"
                aria-label="Show password"
                aria-pressed={visible}
                disabled={busy}
                onClick={() => setVisible(!visible)}
              >
                {visible ? (
                  <EyeOff size={19} aria-hidden="true" />
                ) : (
                  <Eye size={19} aria-hidden="true" />
                )}
              </button>
            </div>
            {signup && (
              <p id="entrance-password-hint" className="entrance-hint">
                Use at least 12 characters.
              </p>
            )}
            {errors.password && (
              <p id="entrance-password-error" className="entrance-error">
                {errors.password}
              </p>
            )}
          </div>
        )}
        {signup && (
          <div className="auth-field">
            <label htmlFor="entrance-confirm">Confirm password</label>
            <input
              id="entrance-confirm"
              ref={confirmationField}
              type={visible ? 'text' : 'password'}
              autoComplete="new-password"
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
        {mode === 'login' && (
          <Link
            className="connected-entrance__recovery"
            to={{ pathname: '/auth/forgot-password', search }}
          >
            Forgot password?
          </Link>
        )}
        {mode === 'login' && <TurnstileWidget key={turnstileRevision} onToken={onTurnstileToken} />}
        {error && (
          <p className="entrance-error" role="alert">
            {error}
          </p>
        )}
        {notice && (
          <p className="entrance-notice" role="status">
            {notice}
          </p>
        )}
        <Button type="submit" disabled={busy}>
          {busy
            ? 'Please wait…'
            : signup
              ? 'Create account'
              : recovery
                ? 'Send reset link'
                : 'Sign in to ClassSync →'}
        </Button>
      </form>
      {mode === 'login' && !invited && (
        <div className="connected-entrance__first-time">
          <span className="connected-entrance__divider">or</span>
          <Button type="button" variant="secondary" disabled={busy} onClick={continueWithGoogle}>
            Continue with Google
          </Button>
          <p className="entrance-hint">Use the email registered in your student record.</p>
          <aside className="connected-entrance__callout">
            <strong>Signing in for the first time?</strong>
            <p>Continue with Google using the email registered in your student record. Verify your account before accessing campus schedules.</p>
          </aside>
          <p className="connected-entrance__help">Need help signing in? Visit the Office of the Registrar.</p>
        </div>
      )}
      <div className="connected-entrance__secondary">
        {mode === 'login' ? (
          invited ? (
            <Link to="/auth/login">Back to regular sign in</Link>
          ) : (
            <>
              New to ClassSync? <Link to="/auth/signup">Create an account</Link>
            </>
          )
        ) : (
          <Link to={{ pathname: '/auth/login', search }}>Back to sign in</Link>
        )}
      </div>
    </>
  );
}
