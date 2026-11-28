import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { PasswordStrengthChecklist } from '../auth/PasswordStrengthChecklist';
import { PasswordInput } from '../auth/PasswordInput';
import { passwordStrengthComplete } from '../auth/password-strength';
import { applyEmailVerificationCode, completePasswordReset, verifyPasswordResetCode } from '../auth/account-actions';
import { useUniversitySession } from '../auth/university-session-context';
import { EntranceLayout } from './InstitutionalEntrance';
import './institutional-entrance.css';

type ActionState = 'checking' | 'verified' | 'reset-ready' | 'complete' | 'invalid';

export function EmailActionPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const session = useUniversitySession();
  const mode = params.get('mode');
  const code = params.get('oobCode') ?? '';
  const [state, setState] = useState<ActionState>('checking');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const started = useRef(false);
  const [visible, setVisible] = useState(false);
  const passwordField = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (state === 'reset-ready') passwordField.current?.focus();
  }, [state]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const check = mode === 'verifyEmail'
      ? applyEmailVerificationCode(code).then(() => {
          setState('verified');
          session.refresh();
          navigate('/auth/action?mode=verifyEmail', { replace: true });
        })
      : mode === 'resetPassword'
        ? verifyPasswordResetCode(code).then(() => setState('reset-ready'))
        : Promise.reject(new Error('Invalid account action'));
    void check.catch(() => setState('invalid'));
    // Firebase action codes are single-use: do not cancel the first request during
    // React StrictMode's development-only setup/cleanup/setup replay.
  }, [code, mode, navigate, session]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || !passwordStrengthComplete(password, confirmPassword)) return;
    setBusy(true);
    setError('');
    try {
      await completePasswordReset(code, password);
      setPassword('');
      setConfirmPassword('');
      setState('complete');
    } catch {
      setError('The password could not be changed. Request a new reset link and try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <EntranceLayout>
      <section className="email-action-card" aria-busy={state === 'checking' || busy}>
        <h1>{mode === 'verifyEmail' ? 'Verify your email' : 'Reset your password'}</h1>
        {state === 'checking' && <p role="status">Checking your secure link…</p>}
        {state === 'verified' && (
          <>
            <p role="status">Email verified!</p>
            <Button onClick={() => navigate('/auth/student-onboarding', { replace: true })}>
              Continue to student access
            </Button>
          </>
        )}
        {state === 'reset-ready' && (
          <form onSubmit={submit} noValidate>
            <p>Choose a new password for your ClassSync account.</p>
            <label htmlFor="action-new-password">New password</label>
            <PasswordInput id="action-new-password" ref={passwordField} visible={visible}
              onToggle={() => setVisible(!visible)} autoComplete="new-password" minLength={12}
              value={password} disabled={busy} onChange={(event) => setPassword(event.target.value)} />
            <label htmlFor="action-confirm-password">Confirm password</label>
            <PasswordInput id="action-confirm-password" visible={visible} autoComplete="new-password" minLength={12}
              value={confirmPassword} disabled={busy} onChange={(event) => setConfirmPassword(event.target.value)} />
            <PasswordStrengthChecklist password={password} confirmPassword={confirmPassword} />
            {error && <p className="entrance-error" role="alert">{error}</p>}
            <Button type="submit" loading={busy} disabled={busy || !passwordStrengthComplete(password, confirmPassword)}>
              {busy ? 'Saving…' : 'Save new password'}
            </Button>
          </form>
        )}
        {state === 'complete' && (
          <>
            <p role="status">Your password has been updated.</p>
            <Link className="button" to="/auth/login">Return to sign in</Link>
          </>
        )}
        {state === 'invalid' && (
          <>
            <p role="alert">This link has expired or was already used.</p>
            <Link className="button" to={mode === 'verifyEmail' ? '/auth/verify' : '/auth/forgot-password'}>
              Request a new link
            </Link>
          </>
        )}
        {state !== 'complete' && <p><Link to="/auth/login">Return to sign in</Link></p>}
      </section>
    </EntranceLayout>
  );
}
