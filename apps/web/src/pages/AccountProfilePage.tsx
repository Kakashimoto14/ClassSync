import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import {
  observeAccountProfile,
  updateAccountName,
  recoverPassword,
  type AccountProfile,
} from '../auth/account-actions';
import { useUniversitySession } from '../auth/university-session-context';
import { Button } from '../components/ui/Button';
import type { UserRole } from '../types/ui';

export function AccountProfilePage({
  role,
  settings = false,
}: {
  role: UserRole;
  settings?: boolean;
}) {
  const university = useUniversitySession();
  const [profile, setProfile] = useState<AccountProfile | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const base = role === 'administrator' ? '/admin' : `/${role}`;
  useEffect(() => {
    let closed = false;
    let unsubscribe: (() => void) | undefined;
    observeAccountProfile((value) => {
      if (!closed) {
        setProfile(value);
        setName(value?.name ?? '');
      }
    })
      .then((stop) => {
        if (closed) stop();
        else unsubscribe = stop;
      })
      .catch(() => {
        if (!closed) setError('Your account information is unavailable. Refresh or sign in again.');
      });
    return () => {
      closed = true;
      unsubscribe?.();
    };
  }, []);
  const authorized =
    university.state.status === 'authorized' &&
    university.state.membership.role === role &&
    profile?.uid === university.state.membership.uid;
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!authorized || busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const updated = await updateAccountName(name, profile.uid);
      setProfile(updated);
      setName(updated.name);
      setNotice('Account name saved.');
    } catch (failure) {
      setError(
        (failure as { code?: string }).code?.startsWith('auth/')
          ? 'Your name could not be saved. Check your connection or sign in again.'
          : failure instanceof Error
            ? failure.message
            : 'Name not confirmed.',
      );
    } finally {
      setBusy(false);
    }
  }
  async function reset() {
    if (!authorized || !profile?.email || busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await recoverPassword(profile.email);
      setNotice('Password recovery requested. Check your email for the next steps.');
    } catch {
      setError('Password recovery could not be requested. Try again.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="workspace-card" aria-busy={busy}>
      <h1>{settings ? 'Account settings' : 'Your profile'}</h1>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!authorized ? (
        error ? (
          <Link to="/auth/login">Restore account access</Link>
        ) : (
          <p role="status">Loading your account…</p>
        )
      ) : (
        <>
          <dl className="detail-list">
            <dt>Email</dt>
            <dd>{profile.email}</dd>
            <dt>Email status</dt>
            <dd>{profile.emailVerified ? 'Verified' : 'Verification required'}</dd>
            <dt>University access</dt>
            <dd>
              {role === 'administrator'
                ? 'Administrator'
                : role === 'teacher'
                  ? 'Teacher'
                  : 'Student'}{' '}
              · Active
            </dd>
            {role === 'student' && university.state.status === 'authorized' && (
              <>
                <dt>Linked student record</dt>
                <dd>{university.state.membership.student_id}</dd>
              </>
            )}
          </dl>
          <form onSubmit={save} className="academic-create-period">
            <label htmlFor="account-display-name">Account name</label>
            <input
              id="account-display-name"
              autoComplete="name"
              maxLength={100}
              required
              disabled={busy}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <p>Your account name does not change your university record or permissions.</p>
            <Button disabled={busy}>{busy ? 'Saving…' : 'Save account name'}</Button>
          </form>
          <div className="draft-actions">
            <Button
              disabled={busy || !profile.email}
              variant="secondary"
              onClick={() => void reset()}
            >
              Send password reset email
            </Button>
            <Button disabled={busy} variant="secondary" onClick={university.signOut}>
              Sign out securely
            </Button>
          </div>
          <p>
            Schedule dates use Asia/Manila. Choose a term, date and view from your schedule; these
            display choices are remembered on this device. Email and push alerts are not enabled.
          </p>
          <nav className="draft-actions" aria-label="Account navigation">
            <Link to={base + (role === 'administrator' ? '/schedule-manager' : '/schedule')}>
              Open schedule options
            </Link>
            <Link to={base + (settings ? '/profile' : '/settings')}>
              {settings ? 'Your profile' : 'Account settings'}
            </Link>
          </nav>
        </>
      )}
    </section>
  );
}
