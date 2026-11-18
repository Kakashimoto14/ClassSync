import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { ArrowRight, CalendarDays, CircleAlert, Eye, EyeOff, MapPin } from 'lucide-react';
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
} from '../auth/account-actions';
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

function presentationUrl() {
  try {
    const url = new URL(import.meta.env.VITE_CLASSSYNC_PRESENTATION_URL);
    const local = devServer && url.protocol === 'http:' && url.hostname === '127.0.0.1';
    if (
      (url.protocol === 'https:' || local) &&
      !url.username &&
      !url.password &&
      url.origin !== window.location.origin
    )
      return url.href;
  } catch {
    // A separate presentation origin is optional.
  }
}

function ProductPreview() {
  return (
    <aside className="connected-entrance__story" aria-label="ClassSync schedule preview">
      <h2>
        Campus, in sync<span>.</span>
      </h2>
      <p>Know what&apos;s next, where to go, and what&apos;s changed.</p>
      <figure className="entrance-preview">
        <figcaption>
          <span className="entrance-preview__icon">
            <CalendarDays size={20} aria-hidden="true" />
          </span>
          <span>
            <strong>Today on campus</strong>
            <small>Sample agenda &middot; Monday</small>
          </span>
        </figcaption>
        <div className="entrance-preview__week" aria-label="Sample week, Monday selected">
          <span className="entrance-preview__day">Mon</span>
          <span>Tue</span>
          <span>Wed</span>
          <span>Thu</span>
          <span>Fri</span>
        </div>
        <ol className="entrance-preview__agenda">
          <li>
            <time dateTime="09:00">9:00</time>
            <div>
              <strong>Human&ndash;Computer Interaction</strong>
              <small>Room NB 204</small>
            </div>
            <span className="entrance-preview__next">Next</span>
          </li>
          <li>
            <time dateTime="11:00">11:00</time>
            <div>
              <strong>Database Systems</strong>
              <small>Room PRRC 103</small>
            </div>
          </li>
        </ol>
        <div className="entrance-preview__update">
          <MapPin size={17} aria-hidden="true" />
          <div>
            <strong>Room changed</strong>
            <small>Human&ndash;Computer Interaction moved to NB 204.</small>
          </div>
        </div>
      </figure>
    </aside>
  );
}

export function EntranceLayout({ children, preview }: { children: ReactNode; preview?: string }) {
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
          {preview && (
            <a className="connected-entrance__sample" href={preview} rel="noreferrer">
              Explore the sample workspace <ArrowRight size={15} aria-hidden="true" />
            </a>
          )}
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
  const preview = presentationUrl();
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
        : 'Welcome back';
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
    <EntranceLayout preview={preview}>
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
      else await signInToAccount(email, password);
    } catch (failure) {
      setError(
        mode === 'login'
          ? 'We could not sign you in. Check your email and password, or try resetting your password.'
          : accountError(failure),
      );
    } finally {
      setBusy(false);
    }
  }

  async function continueWithGoogle() {
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await signInWithGoogle();
    } catch (failure) {
      setError(accountError(failure));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
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
              : 'Sign in to your ClassSync account.'}
      </p>
      <form className="connected-entrance__form" noValidate onSubmit={submit} aria-busy={busy}>
        {!recovery && !invited && (
          <>
            <Button type="button" variant="secondary" disabled={busy} onClick={continueWithGoogle}>
              Continue with Google
            </Button>
            <p className="entrance-hint">Or continue with your email</p>
          </>
        )}
        <div className="auth-field">
          <label htmlFor="entrance-email">Email</label>
          <input
            id="entrance-email"
            ref={emailField}
            type="email"
            placeholder={signup ? 'juan.delacruz@student.pnm.edu.ph' : undefined}
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
                : 'Sign in'}
        </Button>
      </form>
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
