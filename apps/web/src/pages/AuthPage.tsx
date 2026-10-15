import { useRef, useState, type FormEvent } from 'react';
import { ArrowRight, Eye, EyeOff } from 'lucide-react';
import { Link, useSearchParams } from 'react-router-dom';
import { ClassSyncLogo } from '../components/brand/ClassSyncLogo';
import { Button } from '../components/ui/Button';
import { Alert } from '../components/ui/Alert';
import { validateLogin, type LoginValidationErrors } from '../auth/access';

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
    <div className="auth-page">
      <aside className="auth-brand">
        <ClassSyncLogo variant="full" size="large" surface="dark" />
        <div className="auth-brand-copy">
          <h2>Your university day, in one place.</h2>
          <p>Class schedules, assigned rooms, and the updates that matter.</p>
        </div>
      </aside>
      <main className="auth-main">
        <section className="auth-card" aria-labelledby="sign-in-title">
          <div className="auth-card__title">
            <h1 id="sign-in-title">Sign in</h1>
            <p>
              Production sign-in is not configured in this environment. No credentials are sent.
            </p>
          </div>
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
                Your details were not sent or saved. Use the development preview to explore the
                interface.
              </Alert>
            )}
          </form>
          <div className="auth-demo-access">
            <strong>Development preview</strong>
            <p>
              Explore sample Student, Teacher, and Administrator workspaces. This does not sign you
              in.
            </p>
            <Link className="button button--secondary" to={demoHref}>
              Open development demo
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}
