import { useRef, useState, type FormEvent } from 'react';
import { ArrowRight, Eye, EyeOff, CalendarDays, ShieldCheck, MapPin } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { ClassSyncLogo } from '../components/brand/ClassSyncLogo';
import { Button } from '../components/ui/Button';
import { Alert } from '../components/ui/Alert';
import { demoDestination, validateLogin, type LoginValidationErrors } from '../auth/access';
import { previewEnabled } from '../auth/preview-session';
import { useDevelopmentRole } from '../auth/useDevelopmentRole';
import { EntranceTimetable } from '../components/brand/EntranceTimetable';

export function AuthPage() {
  const { role } = useDevelopmentRole();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<LoginValidationErrors>({});
  const [unavailable, setUnavailable] = useState(false);
  const emailInput = useRef<HTMLInputElement>(null);
  const passwordInput = useRef<HTMLInputElement>(null);
  const returnTo = searchParams.get('returnTo');
  const demoHref = returnTo
    ? '/dev/role-preview?returnTo=' + encodeURIComponent(returnTo)
    : '/dev/role-preview';

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validation = validateLogin(email, password);
    setErrors(validation);
    setUnavailable(false);
    if (validation.email) {
      emailInput.current?.focus();
      return;
    }
    if (validation.password) {
      passwordInput.current?.focus();
      return;
    }
    // No provider is configured. Do not simulate network activity or send credentials.
    setUnavailable(true);
  };

  return (
    <main className="welcome-page">
      <header className="welcome-brand">
        <ClassSyncLogo variant="full" size="large" />
      </header>
      <section className="welcome-story" aria-labelledby="welcome-title">
        <div className="welcome-copy">
          <h1 id="welcome-title">
            Smarter schedules.
            <br />
            <span>Better campus days.</span>
          </h1>
          <p>
            Generate weekly timetables, check classroom conflicts, and find the rooms you need—all
            in ClassSync.
          </p>
        </div>
        <ul className="welcome-capabilities" aria-label="ClassSync capabilities">
          <li>
            <CalendarDays size={17} aria-hidden="true" />
            Automated Scheduling
          </li>
          <li>
            <ShieldCheck size={17} aria-hidden="true" />
            Conflict Detection
          </li>
          <li>
            <MapPin size={17} aria-hidden="true" />
            Classroom Discovery
          </li>
        </ul>
      </section>
      <section className="welcome-access" aria-labelledby="sign-in-title">
        <div className="welcome-access-card">
          <span className="welcome-access-icon" aria-hidden="true">
            <ArrowRight size={24} />
          </span>
          <div className="auth-card__title">
            <h2 id="sign-in-title">{role ? 'Welcome back.' : 'Welcome to ClassSync'}</h2>
            <p>
              {previewEnabled
                ? role
                  ? `Your ${role} preview is ready to continue.`
                  : 'Choose a role and explore your campus workspace.'
                : 'University access is not available yet.'}
            </p>
          </div>
          {previewEnabled && (
            <>
              <Link
                className="button entrance-primary"
                to={role ? demoDestination(role, returnTo) : demoHref}
              >
                {role ? 'Continue to workspace' : 'Explore ClassSync'}{' '}
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
              <p className="entrance-note">Sample preview · You are not signed in.</p>
              {role && (
                <Link className="text-action welcome-switch" to={demoHref}>
                  Choose another role
                </Link>
              )}
            </>
          )}
          <details className="university-access">
            <summary>
              University sign-in <span>Not connected</span>
            </summary>
            <div>
              <p className="muted">
                Production authentication is not connected. No credentials are sent or stored.
              </p>
              <form noValidate onSubmit={submit}>
                <div className="auth-field">
                  <label htmlFor="email">University email</label>
                  <input
                    ref={emailInput}
                    id="email"
                    type="email"
                    autoComplete="username"
                    value={email}
                    onChange={(event) => {
                      setEmail(event.target.value);
                      setErrors((value) => ({ ...value, email: undefined }));
                      setUnavailable(false);
                    }}
                    aria-invalid={Boolean(errors.email)}
                    aria-describedby={errors.email ? 'email-error' : undefined}
                    placeholder="name@university.edu"
                  />
                  {errors.email && (
                    <p id="email-error" className="field-error" role="alert">
                      {errors.email}
                    </p>
                  )}
                </div>
                <div className="auth-field">
                  <label htmlFor="password">Password</label>
                  <div className="password-field">
                    <input
                      ref={passwordInput}
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      value={password}
                      onChange={(event) => {
                        setPassword(event.target.value);
                        setErrors((value) => ({ ...value, password: undefined }));
                        setUnavailable(false);
                      }}
                      aria-invalid={Boolean(errors.password)}
                      aria-describedby={errors.password ? 'password-error' : undefined}
                    />
                    <button
                      type="button"
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      aria-pressed={showPassword}
                      onClick={() => setShowPassword((value) => !value)}
                    >
                      {showPassword ? (
                        <EyeOff size={18} aria-hidden="true" />
                      ) : (
                        <Eye size={18} aria-hidden="true" />
                      )}
                    </button>
                  </div>
                  {errors.password && (
                    <p id="password-error" className="field-error" role="alert">
                      {errors.password}
                    </p>
                  )}
                </div>
                <Button type="submit">
                  Check sign-in availability <ArrowRight size={17} aria-hidden="true" />
                </Button>
                {unavailable && (
                  <Alert tone="warning" title="Sign-in unavailable">
                    {previewEnabled
                      ? 'Your details were not sent or saved. Use the development preview to explore the interface.'
                      : 'Your details were not sent or saved. Contact your university for sign-in availability.'}
                  </Alert>
                )}
              </form>
            </div>
          </details>
        </div>
      </section>
      <EntranceTimetable />
    </main>
  );
}
