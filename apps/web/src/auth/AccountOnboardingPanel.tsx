import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
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
import { TurnstileWidget } from './TurnstileWidget';
import { PasswordStrengthChecklist } from './PasswordStrengthChecklist';
import { passwordStrengthComplete } from './password-strength';

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
  const [step, setStep] = useState<'student' | 'code' | 'password'>('student');
  const [challenge, setChallenge] = useState<{
    challenge_id: string;
    masked_email: string;
    expires_in_seconds: number;
    resend_after_seconds: number;
  } | null>(null);
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [turnstileToken, setTurnstileToken] = useState('');
  const [turnstileRevision, setTurnstileRevision] = useState(0);
  const onTurnstileToken = useCallback((value: string) => setTurnstileToken(value), []);
  const [resendSeconds, setResendSeconds] = useState(0);
  const digitRefs = useRef<Array<HTMLInputElement | null>>([]);
  const [busy, setBusy] = useState(false);
  const signedIn = ['denied', 'verification-required'].includes(session.state.status);
  useEffect(() => {
    if (resendSeconds <= 0) return;
    const timer = window.setTimeout(() => setResendSeconds((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [resendSeconds]);
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
  const sendCode = async () => {
    if (busy || !status?.email_verified || status.membership_state) return;
    if (!/^[0-9]{2}-[0-9]{5}$/.test(studentId.trim())) {
      const error = 'Use the format 12-12345 for your student number.';
      setStudentIdError(error);
      setMessage(error);
      return;
    }
    setStudentIdError('');
    setBusy(true);
    setMessage('');
    try {
      const next = await accountRequest<NonNullable<typeof challenge>>(
        'student-verification-challenges', 'POST', {
          student_id: studentId.trim(), turnstile_token: turnstileToken,
        },
        undefined, profile.uid,
      );
      setChallenge(next);
      setStep('code');
      setCode('');
      setResendSeconds(next.resend_after_seconds);
      setMessage(`A code was sent to ${next.masked_email}. It expires in 5 minutes.`);
      digitRefs.current[0]?.focus();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : accountError(error));
    } finally {
      setTurnstileToken('');
      setTurnstileRevision((revision) => revision + 1);
      setBusy(false);
    }
  };
  const requestCode = (event: FormEvent) => {
    event.preventDefault();
    void sendCode();
  };
  const verifyCode = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || !challenge || code.length !== 6) return;
    setBusy(true);
    setMessage('');
    try {
      await accountRequest(
        'verify-student', 'POST',
        { student_id: studentId.trim(), challenge_id: challenge.challenge_id, code,
          turnstile_token: turnstileToken },
        undefined, profile.uid,
      );
      setStep('password');
      setCode('');
      setMessage('Student record verified. Create a private password for future sign-ins.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : accountError(error));
    } finally {
      setTurnstileToken('');
      setTurnstileRevision((revision) => revision + 1);
      setBusy(false);
    }
  };
  const resendCode = () => {
    if (resendSeconds === 0 && !busy) void sendCode();
  };
  const completePasswordSetup = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || !challenge) return;
    if (newPassword.length > 128 || !passwordStrengthComplete(newPassword, confirmPassword)) {
      setMessage('Meet all six password requirements before continuing.');
      return;
    }
    setBusy(true);
    setMessage('');
    try {
      await accountRequest(
        'complete-student-onboarding', 'POST', {
          student_id: studentId.trim(), challenge_id: challenge.challenge_id,
          turnstile_token: turnstileToken, password: newPassword,
        }, undefined, profile.uid,
      );
      setStatus(await accountRequest<OnboardingStatus>(
        'onboarding', 'GET', undefined, undefined, profile.uid,
      ));
      setNewPassword('');
      setConfirmPassword('');
      setMessage('Your student record and portal password are ready.');
      session.refresh();
    } catch (error) {
      setMessage(error instanceof Error && !('code' in error) ? error.message : accountError(error));
    } finally {
      setTurnstileToken('');
      setTurnstileRevision((revision) => revision + 1);
      setBusy(false);
    }
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
          {entryRole !== 'teacher' && !status.membership_state && step === 'student' && (
            <Link className="button" to="/student/registration-scanner">
              Scan registration form
            </Link>
          )}
          {entryRole !== 'teacher' && !status.membership_state && (
            step === 'student' ? <form noValidate onSubmit={requestCode}>
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
              <TurnstileWidget key={turnstileRevision} onToken={onTurnstileToken} />
              <Button type="submit" disabled={busy}>
                {busy ? 'Sending code…' : 'Send verification code'}
              </Button>
            </form> : step === 'code' && challenge ? <form noValidate onSubmit={verifyCode} className="account-onboarding__otp">
              <h4>Verify your sign-in</h4>
              <p>Enter the 6-digit code sent to {challenge.masked_email}. It expires in 5 minutes and can be used once.</p>
              <div className="account-onboarding__otp-digits" role="group" aria-label="Verification code">
                {Array.from({ length: 6 }, (_, index) => (
                  <input
                    key={index}
                    ref={(node) => { digitRefs.current[index] = node; }}
                    aria-label={`Verification digit ${index + 1}`}
                    inputMode="numeric"
                    autoComplete={index === 0 ? 'one-time-code' : 'off'}
                    pattern="[0-9]*"
                    maxLength={index === 0 ? 6 : 1}
                    value={code[index] ?? ''}
                    disabled={busy}
                    onPaste={(event) => {
                      const pasted = event.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
                      if (!pasted) return;
                      event.preventDefault();
                      setCode(pasted);
                      digitRefs.current[Math.min(pasted.length, 5)]?.focus();
                    }}
                    onChange={(event) => {
                      const digits = event.target.value.replace(/\D/g, '');
                      if (!digits) {
                        setCode((value) => value.slice(0, index) + value.slice(index + 1));
                        return;
                      }
                      const next = digits.length > 1
                        ? digits.slice(0, 6)
                        : (code.slice(0, index) + digits[0] + code.slice(index + 1)).slice(0, 6);
                      setCode(next);
                      digitRefs.current[Math.min(index + digits.length, 5)]?.focus();
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Backspace' && !code[index] && index > 0)
                        digitRefs.current[index - 1]?.focus();
                    }}
                  />
                ))}
              </div>
              <TurnstileWidget key={turnstileRevision} onToken={onTurnstileToken} />
              <Button type="submit" disabled={busy || code.length !== 6}>{busy ? 'Verifying…' : 'Verify and sign in'}</Button>
              <div className="account-onboarding__otp-actions">
                <Button type="button" variant="secondary" disabled={busy || resendSeconds > 0} onClick={resendCode}>
                  {resendSeconds ? `Resend code in ${resendSeconds}s` : 'Resend code'}
                </Button>
                <Button type="button" variant="ghost" disabled={busy} onClick={() => void session.signOut()}>
                  Cancel sign-in
                </Button>
              </div>
              <p className="entrance-hint">If you cannot access your registered email, contact the Registrar for identity-checked account recovery.</p>
            </form> : step === 'password' && challenge ? <form noValidate onSubmit={completePasswordSetup} className="account-onboarding__password-setup">
              <h4>Create your portal password</h4>
              <p>Student Number <strong>{studentId}</strong></p>
              <label htmlFor="student-new-password">New Password</label>
              <input id="student-new-password" type="password" autoComplete="new-password"
                minLength={12} maxLength={128} required disabled={busy} value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)} />
              <label htmlFor="student-confirm-password">Confirm Password</label>
              <input id="student-confirm-password" type="password" autoComplete="new-password"
                minLength={12} maxLength={128} required disabled={busy} value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)} />
              <PasswordStrengthChecklist password={newPassword} confirmPassword={confirmPassword} />
              <p className="entrance-hint">Your password stays with your ClassSync account.</p>
              <TurnstileWidget key={turnstileRevision} onToken={onTurnstileToken} />
              <Button type="submit" disabled={busy || !passwordStrengthComplete(newPassword, confirmPassword)}>{busy ? 'Securing your account…' : 'Create portal password'}</Button>
            </form> : null
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
