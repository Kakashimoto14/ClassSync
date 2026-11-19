import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { CalendarDays, CircleAlert, DoorOpen, Eye, EyeOff, ShieldCheck } from 'lucide-react';
import { Link, Navigate, useLocation } from 'react-router-dom';
import { MotionConfig, motion } from 'motion/react';
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
import '../styles/pages/auth.css';

const invitePath = '/auth/teacher-invite';
const verifyPath = '/auth/verify';
const onboardingPath = '/auth/student-onboarding';
const accountPath = '/auth/account';
const STUDENT_EMAIL_PATTERN = /^[a-z]+(?:\.[a-z]+)*@student\.pnm\.edu\.ph$/;
const STUDENT_ID_PATTERN = /^[0-9]{2}-[0-9]{5}$/;

function ProductPreview() {
  return (
    <motion.aside
      className="connected-entrance__story"
      aria-label="ClassSync campus services"
      variants={entranceItem}
    >
      <div className="connected-entrance__portal-brand">
        <span>COLEGIO DE MONTALBAN · CLASSSYNC PORTAL</span>
      </div>
      <h2>
        Smarter schedules.<br />Better campus days<span>.</span>
      </h2>
      <p>Academic and scheduling services for the Colegio de Montalban community.</p>
      <ul className="connected-entrance__features entrance-preview-card">
        <li><span className="entrance-preview-card__icon"><CalendarDays size={19} aria-hidden="true" /></span><span><strong>Live Class Schedules</strong><small>Class times and room assignments</small></span></li>
        <li><span className="entrance-preview-card__icon"><DoorOpen size={19} aria-hidden="true" /></span><span><strong>Campus Room Availability</strong><small>Buildings and learning spaces</small></span></li>
        <li><span className="entrance-preview-card__icon"><ShieldCheck size={19} aria-hidden="true" /></span><span><strong>Instant Schedule Alerts</strong><small>Official changes and updates</small></span></li>
      </ul>
      <small className="connected-entrance__service-label">ACADEMIC &amp; SCHEDULING SERVICES</small>
    </motion.aside>
  );
}

const entranceItem = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.24, ease: 'easeOut' as const } },
};

const entranceFrame = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.08, delayChildren: 0.04 } },
};

export function EntranceLayout({ children }: { children: ReactNode }) {
  const synthetic = devServer && import.meta.env.VITE_CLASSSYNC_SYNTHETIC_PREVIEW === 'true';
  return (
    <MotionConfig reducedMotion="user">
    <motion.main
      className="connected-entrance"
      initial="hidden"
      animate="visible"
      variants={entranceFrame}
    >
      <motion.div className="connected-entrance__frame" variants={entranceFrame}>
        <motion.section className="connected-entrance__access" aria-label="ClassSync account access" variants={entranceItem}>
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
        </motion.section>
        <ProductPreview />
      </motion.div>
    </motion.main>
    </MotionConfig>
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

  const loginEntry = path === '/auth/login' || path === '';
  const canSignIn = (available && signedOut) || (loginEntry && mode === 'login');
  const formTitle =
    mode === 'signup'
      ? 'Create your account'
      : mode === 'recovery'
        ? 'Reset your password'
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
        <>
          <CredentialsForm
            key={mode}
            mode={mode}
            title={formTitle}
            search={search}
            invited={invited}
            serviceAvailable={available}
          />
        </>
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
  serviceAvailable = true,
}: {
  mode: 'login' | 'signup' | 'recovery';
  title: string;
  search: string;
  invited: boolean;
  serviceAvailable?: boolean;
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
    const studentNumberLogin = mode === 'login' && STUDENT_ID_PATTERN.test(email.trim());
    const validation: typeof errors = studentNumberLogin
      ? {}
      : validateLogin(email.trim(), password);
    if (studentNumberLogin && !password) validation.password = 'Enter your password.';
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
        if (studentNumberLogin) {
          await signInToAccount(email, password, turnstileToken);
        } else {
          await verifyHumanChallenge(turnstileToken);
          await signInToAccount(email, password);
        }
      }
    } catch (failure) {
      setError(
        mode === 'login' && studentNumberLogin
          ? 'Invalid student number or password.'
          : mode === 'login'
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
      {mode === 'login' && (
        <div className="connected-entrance__eyebrow-row">
          <p className="connected-entrance__eyebrow">CAMPUS ACCESS</p>
          {!invited && (
            <Link to="/auth/signup" className="connected-entrance__signup-link">
              Create account
            </Link>
          )}
        </div>
      )}
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
              : 'Use your student number, campus email, or Google account.'}
      </p>
      <form className="connected-entrance__form" noValidate onSubmit={submit} aria-busy={busy}>
        <div className="auth-field">
          <label htmlFor="entrance-email">
            {mode === 'login' ? 'Student Number or Institutional Email' : 'Email'}
          </label>
          <input
            id="entrance-email"
            ref={emailField}
            type={mode === 'login' ? 'text' : 'email'}
            placeholder={mode === 'login'
              ? '23-01425 or juan.delacruz@student.pnm.edu.ph'
              : signup ? 'juan.delacruz@student.pnm.edu.ph' : undefined}
            autoComplete="username"
            inputMode={mode === 'login' ? 'text' : 'email'}
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
        <Button type="submit" disabled={busy || !serviceAvailable}>
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
          <Button type="button" variant="secondary" disabled={busy || !serviceAvailable} onClick={continueWithGoogle}>
            Continue with Google
          </Button>
          <aside className="connected-entrance__callout">
            <strong>Signing in for the first time?</strong>
            <p>Use your registered Google email, verify the code, and set a password.</p>
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
      {(mode !== 'login' || invited) && (
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
