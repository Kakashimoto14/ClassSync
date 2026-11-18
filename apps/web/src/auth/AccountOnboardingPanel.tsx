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
  observeAccountProfile,
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
  const [token, setToken] = useState('');
  const [message, setMessage] = useState('');
  const [studentIdError, setStudentIdError] = useState('');
  const [busy, setBusy] = useState(false);
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
  const verifyStudent = (event: FormEvent) => {
    event.preventDefault();
    if (busy || !status?.email_verified || status.membership_state) return;
    if (!/^[0-9]{2}-[0-9]{5}$/.test(studentId.trim())) {
      const error = 'Use the format 12-12345 for your student number.';
      setStudentIdError(error);
      setMessage(error);
      return;
    }
    setStudentIdError('');
    void action(async () => {
      await accountRequest(
        'verify-student',
        'POST',
        { student_id: studentId.trim() },
        undefined,
        profile.uid,
      );
    }, 'Student record verified. Refresh your account to continue.');
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
          {entryRole !== 'teacher' && !status.membership_state && (
            <form noValidate onSubmit={verifyStudent}>
              <h4>Verify your student record</h4>
              <label htmlFor="claim-registered-email">Registered student email</label>
              <input
                id="claim-registered-email"
                type="email"
                readOnly
                value={profile.email}
                placeholder="juan.delacruz@student.pnm.edu.ph"
                autoComplete="email"
              />
              <p className="entrance-hint">
                This verified account email must match the address on your Registrar record.
              </p>
              <label htmlFor="claim-student-id">Student number</label>
              <input
                id="claim-student-id"
                required
                minLength={8}
                maxLength={8}
                pattern="[0-9]{2}-[0-9]{5}"
                inputMode="numeric"
                placeholder="12-12345"
                autoComplete="off"
                disabled={busy}
                value={studentId}
                aria-invalid={!!studentIdError}
                aria-describedby={studentIdError ? 'student-number-error' : undefined}
                onChange={(event) => {
                  setStudentId(event.target.value);
                  setStudentIdError('');
                  setMessage('');
                }}
              />
              {studentIdError && (
                <p id="student-number-error" className="entrance-error">
                  {studentIdError}
                </p>
              )}
              <Button type="submit" disabled={busy}>
                {busy ? 'Checking record…' : 'Verify student record'}
              </Button>
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
