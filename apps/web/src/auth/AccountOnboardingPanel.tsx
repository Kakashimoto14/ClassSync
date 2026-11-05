import { useEffect, useState, type FormEvent } from 'react';
import { Button } from '../components/ui/Button';
import { Link } from 'react-router-dom';
import { useUniversitySession } from './university-session-context';
import {
  accountRequest,
  refreshVerifiedAccount,
  resendVerification,
  accountError,
  type OnboardingStatus,
  observeAccount,
} from './account-actions';

export function AccountOnboardingPanel() {
  const [uid, setUid] = useState<string | null>(null);
  useEffect(() => {
    let closed = false;
    let stop: (() => void) | undefined;
    void observeAccount((next) => {
      if (!closed) setUid(next);
    })
      .then((unsubscribe) => {
        if (closed) unsubscribe();
        else stop = unsubscribe;
      })
      .catch(() => {
        if (!closed) setUid(null);
      });
    return () => {
      closed = true;
      stop?.();
    };
  }, []);
  return uid ? <PendingAccount key={uid} /> : null;
}

function PendingAccount() {
  const session = useUniversitySession();
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [studentId, setStudentId] = useState('');
  const [token, setToken] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const signedIn = !['signed-out', 'checking'].includes(session.state.status);
  useEffect(() => {
    if (!signedIn) return;
    let closed = false;
    void accountRequest<OnboardingStatus>('onboarding')
      .then((next) => {
        if (!closed) setStatus(next);
      })
      .catch(() => {
        if (!closed)
          setMessage('Account status could not be loaded. Retry when your connection returns.');
      });
    return () => {
      closed = true;
    };
  }, [signedIn]);
  if (!signedIn || session.state.status === 'authorized') return null;
  const action = async (work: () => Promise<unknown>, success: string) => {
    setBusy(true);
    setMessage('');
    try {
      await work();
      setStatus(await accountRequest<OnboardingStatus>('onboarding'));
      setMessage(success);
      session.refresh();
    } catch (error) {
      setMessage(
        error instanceof Error && !('code' in error) ? error.message : accountError(error),
      );
    } finally {
      setBusy(false);
    }
  };
  const claim = (event: FormEvent) => {
    event.preventDefault();
    void action(
      () => accountRequest('student-claims', 'POST', { student_id: studentId.trim() }),
      'Your request is waiting for university verification.',
    );
  };
  return (
    <section aria-label="Set up university access" aria-busy={busy}>
      <h3>Set up your account</h3>
      <p role="status">
        {message ||
          (status?.status === 'pending'
            ? 'Your student record request is awaiting university verification.'
            : 'Creating an account does not activate university access.')}
      </p>
      {!status?.email_verified ? (
        <>
          <p>Verify your email using the link in your inbox, then check again.</p>
          <Button
            disabled={busy}
            onClick={() =>
              void action(resendVerification, 'Verification email requested. Check your inbox.')
            }
          >
            Resend verification email
          </Button>
          <Button
            disabled={busy}
            variant="secondary"
            onClick={() => void action(refreshVerifiedAccount, 'Email status refreshed.')}
          >
            I verified my email
          </Button>
        </>
      ) : (
        <>
          {!status.membership_state && (
            <Link className="button" to="/student/registration-scanner">
              Scan registration form
            </Link>
          )}
          {!status.claim_state && !status.membership_state && (
            <form onSubmit={claim}>
              <label htmlFor="claim-student-id">Student number</label>
              <input
                id="claim-student-id"
                required
                maxLength={128}
                autoComplete="off"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
              />
              <p>Your university must verify this request before you can view academic records.</p>
              <Button type="submit" disabled={busy}>
                Request student access
              </Button>
            </form>
          )}
          {status.claim_state === 'rejected' && (
            <p>Your request was not approved. Contact your university to correct or review it.</p>
          )}
          {status.membership_state === 'revoked' && (
            <p>Your university access has been revoked. Contact your university for help.</p>
          )}
          {!status.membership_state && (
            <details>
              <summary>Have a Teacher invitation?</summary>
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  void action(
                    () =>
                      accountRequest('faculty-invitations/accept', 'POST', { token: token.trim() }),
                    'Teacher invitation accepted.',
                  );
                }}
              >
                <label htmlFor="faculty-invitation">Invitation code</label>
                <input
                  id="faculty-invitation"
                  required
                  minLength={40}
                  maxLength={128}
                  autoComplete="off"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                />
                <Button disabled={busy} type="submit">
                  Accept invitation
                </Button>
              </form>
            </details>
          )}
          <Button
            disabled={busy}
            variant="secondary"
            onClick={() => void action(refreshVerifiedAccount, 'Account status refreshed.')}
          >
            Check account status
          </Button>
        </>
      )}
    </section>
  );
}
