import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Button } from '../components/ui/Button';
import { Link } from 'react-router-dom';
import { useUniversitySession } from './university-session-context';
import {
  accountRequest,
  refreshVerifiedAccount,
  resendVerification,
  accountError,
  type OnboardingStatus,
  observeAccountProfile,
  updateAccountName,
  type AccountProfile,
} from './account-actions';

export function AccountOnboardingPanel({ entryRole }: { entryRole?: 'student' | 'teacher' } = {}) {
  const [profile, setProfile] = useState<AccountProfile | null>(null);
  useEffect(() => {
    let closed = false;
    let stop: (() => void) | undefined;
    void observeAccountProfile((next) => {
      if (!closed) setProfile(next);
    })
      .then((unsubscribe) => {
        if (closed) unsubscribe();
        else stop = unsubscribe;
      })
      .catch(() => {
        if (!closed) setProfile(null);
      });
    return () => {
      closed = true;
      stop?.();
    };
  }, []);
  return profile ? (
    <PendingAccount key={profile.uid} profile={profile} entryRole={entryRole} />
  ) : null;
}

function PendingAccount({
  profile,
  entryRole,
}: {
  profile: AccountProfile;
  entryRole?: 'student' | 'teacher';
}) {
  const session = useUniversitySession();
  const [status, setStatus] = useState<OnboardingStatus | null>(null);
  const [studentId, setStudentId] = useState('');
  const [name, setName] = useState(profile.name);
  const [reviewing, setReviewing] = useState(false);
  const [token, setToken] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const reviewHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (reviewing) reviewHeading.current?.focus();
  }, [reviewing]);
  const signedIn = ['denied', 'verification-required'].includes(session.state.status);
  useEffect(() => {
    if (!signedIn) return;
    let closed = false;
    void accountRequest<OnboardingStatus>('onboarding', 'GET', undefined, undefined, profile.uid)
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
  }, [signedIn, profile.uid]);
  if (!signedIn) return null;
  const action = async (work: () => Promise<unknown>, success: string) => {
    if (busy) return;
    setBusy(true);
    setMessage('');
    try {
      await work();
      setStatus(
        await accountRequest<OnboardingStatus>(
          'onboarding',
          'GET',
          undefined,
          undefined,
          profile.uid,
        ),
      );
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
    if (busy || !status?.email_verified || status.claim_state || status.membership_state) return;
    if (!studentId.trim() || !name.trim()) {
      setMessage('Enter your name and student number to continue.');
      return;
    }
    if (!reviewing) {
      setReviewing(true);
      setMessage('');
      return;
    }
    void action(async () => {
      if (name.trim() !== profile.name) await updateAccountName(name, profile.uid);
      await accountRequest(
        'student-claims',
        'POST',
        { student_id: studentId.trim() },
        undefined,
        profile.uid,
      );
    }, 'Your request is waiting for university verification.');
  };
  return (
    <section className="account-onboarding" aria-label="Set up university access" aria-busy={busy}>
      <h3>{entryRole === 'teacher' ? 'Activate your invitation' : 'Set up your account'}</h3>
      <p role="status">
        {message ||
          (status?.status === 'pending'
            ? 'Your student record request is awaiting university verification.'
            : entryRole === 'teacher'
              ? 'Enter the private code provided by your university.'
              : 'Link your student record to see your published classes.')}
      </p>
      {!status ? (
        <Button
          disabled={busy}
          variant="secondary"
          onClick={() => void action(() => Promise.resolve(), 'Account status refreshed.')}
        >
          Check account status
        </Button>
      ) : !status.email_verified ? (
        <>
          <p>Verify your email using the link in your inbox, then check again.</p>
          <Button
            disabled={busy}
            onClick={() =>
              void action(
                () => resendVerification(profile.uid),
                'Verification email requested. Check your inbox.',
              )
            }
          >
            Resend verification email
          </Button>
          <Button
            disabled={busy}
            variant="secondary"
            onClick={() =>
              void action(() => refreshVerifiedAccount(profile.uid), 'Email status refreshed.')
            }
          >
            I verified my email
          </Button>
        </>
      ) : (
        <>
          {entryRole !== 'teacher' && !status.membership_state && (
            <Link className="button" to="/student/registration-scanner">
              Scan registration form
            </Link>
          )}
          {entryRole !== 'teacher' && !status.claim_state && !status.membership_state && (
            <form onSubmit={claim}>
              {reviewing ? (
                <>
                  <h4 tabIndex={-1} ref={reviewHeading}>
                    Review your student record claim
                  </h4>
                  <dl>
                    <dt>Account name</dt>
                    <dd>{name.trim()}</dd>
                    <dt>Student number</dt>
                    <dd>{studentId.trim()}</dd>
                  </dl>
                  <p>
                    Your university verifies your academic record before you can access your
                    schedule.
                  </p>
                  <Button type="submit" disabled={busy}>
                    Request student access
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={busy}
                    onClick={() => setReviewing(false)}
                  >
                    Edit profile
                  </Button>
                </>
              ) : (
                <>
                  <h4>Complete your academic profile</h4>
                  <label htmlFor="claim-account-name">Account name</label>
                  <input
                    id="claim-account-name"
                    required
                    maxLength={100}
                    autoComplete="name"
                    disabled={busy}
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                  />
                  <label htmlFor="claim-student-id">Student number</label>
                  <input
                    id="claim-student-id"
                    required
                    maxLength={128}
                    autoComplete="off"
                    disabled={busy}
                    value={studentId}
                    onChange={(event) => setStudentId(event.target.value)}
                  />
                  <Button type="submit" disabled={busy}>
                    Review student record
                  </Button>
                </>
              )}
            </form>
          )}
          {status.claim_state === 'rejected' && (
            <p>Your request was not approved. Contact your university to correct or review it.</p>
          )}
          {status.membership_state === 'revoked' && (
            <p>Your university access has been revoked. Contact your university for help.</p>
          )}
          {entryRole !== 'student' && !status.membership_state && (
            <details open={entryRole === 'teacher' || undefined}>
              <summary>Have a Teacher invitation?</summary>
              <form
                onSubmit={(event) => {
                  event.preventDefault();
                  void action(
                    () =>
                      accountRequest(
                        'faculty-invitations/accept',
                        'POST',
                        { token: token.trim() },
                        undefined,
                        profile.uid,
                      ),
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
            onClick={() =>
              void action(() => refreshVerifiedAccount(profile.uid), 'Account status refreshed.')
            }
          >
            Check account status
          </Button>
        </>
      )}
    </section>
  );
}
