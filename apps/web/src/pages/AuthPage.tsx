import { useRef, useState, type FormEvent } from 'react';
import { ArrowRight, Eye, EyeOff } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { ClassSyncLogo } from '../components/brand/ClassSyncLogo';
import { Button } from '../components/ui/Button';
import { Alert } from '../components/ui/Alert';
import { validateLogin, type LoginValidationErrors } from '../auth/access';
import { previewEnabled } from '../auth/preview-session';

export function AuthPage() {
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
    <div className="auth-page auth-entrance">
      <aside className="auth-brand">
        <ClassSyncLogo variant="full" size="large" />
        <div className="auth-brand-copy">
          <h2>
            Smarter scheduling.
            <br />
            Fewer classroom conflicts.
          </h2>
          <p>Schedules, classrooms, and teaching updates in one place.</p>
        </div>
      </aside>
      <main className="auth-main">
        <section className="auth-card" aria-labelledby="sign-in-title">
          <div className="auth-card__title">
            <h1 id="sign-in-title">Your campus, coordinated.</h1>
            <p>
              {previewEnabled
                ? 'Find your schedule, classroom, and updates.'
                : 'Access your university workspace.'}
            </p>
          </div>
          {previewEnabled && (
            <>
              <Link className="button entrance-primary" to={demoHref}>
                Explore ClassSync <ArrowRight size={18} aria-hidden="true" />
              </Link>
              <p className="entrance-note">Sample preview · You are not signed in.</p>
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
                  Sign in <ArrowRight size={17} aria-hidden="true" />
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
        </section>
      </main>
    </div>
  );
}
