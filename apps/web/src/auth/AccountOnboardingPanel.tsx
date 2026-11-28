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
import { cooldownRemaining, retryAfterFrom, startCooldown } from './cooldown';
import { formatStudentNumber } from './student-number';
import { PasswordInput } from './PasswordInput';

const STEPS = ['Email', 'Student record', 'Password'];

/** Server messages are already sanitised; network and provider failures get mapped copy. */
function friendly(error: unknown) {
  return error instanceof Error && !('code' in error) && error.name !== 'TypeError'
    ? error.message
    : accountError(error);
}

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
  const [verificationResendSeconds, setVerificationResendSeconds] = useState(() =>
    cooldownRemaining('verification-email', profile.email),
  );
  const [codeResendSeconds, setCodeResendSeconds] = useState(() =>
    cooldownRemaining('student-code', profile.email),
  );
  const digitRefs = useRef<Array<HTMLInputElement | null>>([]);
  const passwordField = useRef<HTMLInputElement>(null);
  const [passwordVisible, setPasswordVisible] = useState(false);
  useEffect(() => {
    if (step === 'code') digitRefs.current[0]?.focus();
    if (step === 'password') passwordField.current?.focus();
  }, [step]);
  const [busy, setBusy] = useState(false);
  const signedIn = ['denied', 'verification-required'].includes(session.state.status);
  useEffect(() => {
    setVerificationResendSeconds(cooldownRemaining('verification-email', profile.email));
    setCodeResendSeconds(cooldownRemaining('student-code', profile.email));
  }, [profile.email]);
  const hasOnboardingCooldown = verificationResendSeconds > 0 || codeResendSeconds > 0;
  useEffect(() => {
    if (!hasOnboardingCooldown) return;
    const timer = window.setInterval(() => {
      setVerificationResendSeconds(cooldownRemaining('verification-email', profile.email));
      setCodeResendSeconds(cooldownRemaining('student-code', profile.email));
    }, 500);
    return () => window.clearInterval(timer);
  }, [hasOnboardingCooldown, profile.email]);
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
  const action = async (
    work: () => Promise<unknown>,
    success: string | ((next: OnboardingStatus) => string),
  ) => {
    if (busy) return;
    setBusy(true);
    setMessage('');
    try {
      await work();
      const next = await accountRequest<OnboardingStatus>(
        'onboarding',
        'GET',
        undefined,
        undefined,
        profile.uid,
      );
      setStatus(next);
      setMessage(typeof success === 'string' ? success : success(next));
      session.refresh();
    } catch (error) {
      setMessage(friendly(error));
    } finally {
      setBusy(false);
    }
  };
  const requestVerificationEmail = async () => {
    try {
      await resendVerification(profile.uid);
      setVerificationResendSeconds(startCooldown('verification-email', profile.email, 30));
    } catch (error) {
      const retryAfter = retryAfterFrom(error);
      if (retryAfter)
        setVerificationResendSeconds(
          startCooldown('verification-email', profile.email, retryAfter),
        );
      throw error;
    }
  };
  const sendCode = async () => {
    if (busy || !status?.email_verified || status.membership_state || codeResendSeconds > 0) return;
    if (!/^[0-9]{2}-[0-9]{5}$/.test(studentId.trim())) {
      const error = 'Use the format 12-12345 for your student number.';
      setStudentIdError(error);
      setMessage(error);
      return;
    }
    if (!turnstileToken) {
      setMessage('Complete the human verification check before continuing.');
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
      setCodeResendSeconds(startCooldown('student-code', profile.email, next.resend_after_seconds));
      setMessage(`A code was sent to ${next.masked_email}. It expires in 5 minutes.`);
      digitRefs.current[0]?.focus();
    } catch (error) {
      const retryAfter = retryAfterFrom(error);
      if (retryAfter) setCodeResendSeconds(startCooldown('student-code', profile.email, retryAfter));
      setMessage(friendly(error));
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
    if (busy || !challenge) return;
    if (code.length !== 6) {
      setMessage('Enter all 6 digits of the verification code.');
      return;
    }
    if (!turnstileToken) {
      setMessage('Complete the human verification check before continuing.');
      return;
    }
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
      setMessage(friendly(error));
    } finally {
      setTurnstileToken('');
      setTurnstileRevision((revision) => revision + 1);
      setBusy(false);
    }
  };
  const resendCode = () => {
    if (codeResendSeconds === 0 && !busy) void sendCode();
  };
  const completePasswordSetup = async (event: FormEvent) => {
    event.preventDefault();
    if (busy || !challenge) return;
    if (newPassword.length > 128 || !passwordStrengthComplete(newPassword, confirmPassword)) {
      setMessage('Meet all six password requirements before continuing.');
      return;
    }
    if (!turnstileToken) {
      setMessage('Complete the human verification check before continuing.');
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
      setMessage(friendly(error));
    } finally {
      setTurnstileToken('');
      setTurnstileRevision((revision) => revision + 1);
      setBusy(false);
    }
  };
  const currentStep = !status?.email_verified ? 0 : step === 'password' ? 2 : 1;
  return (
    <section className="account-onboarding" aria-label="Set up university access" aria-busy={busy}>
      <h3>{entryRole === 'teacher' ? 'Activate your invitation' : 'Set up your account'}</h3>
      {entryRole !== 'teacher' && status && !status.membership_state && (
        <ol className="account-onboarding__steps" aria-label="Account setup steps">
          {STEPS.map((label, index) => (
            <li
              key={label}
              aria-current={index === currentStep ? 'step' : undefined}
              data-state={index < currentStep ? 'done' : index === currentStep ? 'current' : 'next'}
            >
              {label}
              {index < currentStep && <span className="visually-hidden"> (complete)</span>}
            </li>
          ))}
        </ol>
      )}
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
          <p>
            Open the verification link we sent to <strong>{profile.email}</strong>, then come back
            here.
          </p>
          <div className="account-onboarding__actions">
            <Button
              disabled={busy}
              onClick={() =>
                void action(
                  () => refreshVerifiedAccount(profile.uid),
                  (next) =>
                    next.email_verified
                      ? 'Email verified.'
                      : 'Your email is not verified yet. Open the link in your inbox, then try again.',
                )
              }
            >
              I&rsquo;ve verified — Continue
            </Button>
            <Button
              variant="secondary"
              disabled={busy || verificationResendSeconds > 0}
              onClick={() =>
                void action(
                  requestVerificationEmail,
                  'Verification email requested. Check your inbox.',
                )
              }
            >
              {verificationResendSeconds > 0
                ? `Resend verification email in ${verificationResendSeconds}s`
                : 'Resend verification email'}
            </Button>
          </div>
        </>
      ) : (
        <>
          {entryRole !== 'teacher' && !status.membership_state && (
            step === 'student' ? <>
              <form noValidate onSubmit={requestCode}>
              <h4>Verify your student record</h4>
              <label htmlFor="claim-registered-email">Email address</label>
              <input
                id="claim-registered-email"
                type="email"
                readOnly
                value={profile.email}
                placeholder="student@example.com"
                autoComplete="email"
              />
              <p className="entrance-hint">
                This is your sign-in email, so it cannot be changed here. It is checked against the
                student record when one is available.
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
                  setStudentId(formatStudentNumber(event.target.value));
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
              <Button type="submit" disabled={busy || codeResendSeconds > 0}>
                {busy ? 'Sending code…' : codeResendSeconds > 0
                  ? `Send verification code in ${codeResendSeconds}s`
                  : 'Send verification code'}
              </Button>
              </form>
              {status.verification_mode === 'cor_or_roster' && (
                <Link className="button button--secondary" to="/student/registration-scanner">
                  Scan Registration Form (COR)
                </Link>
              )}
            </> : step === 'code' && challenge ? <form noValidate onSubmit={verifyCode} className="account-onboarding__otp">
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
              <Button type="submit" disabled={busy}>{busy ? 'Verifying…' : 'Verify and sign in'}</Button>
              <div className="account-onboarding__otp-actions">
                <Button type="button" variant="secondary" disabled={busy || codeResendSeconds > 0} onClick={resendCode}>
                  {codeResendSeconds ? `Resend code in ${codeResendSeconds}s` : 'Resend code'}
                </Button>
                <Button type="button" variant="ghost" disabled={busy} onClick={() => void session.signOut()}>
                  Cancel sign-in
                </Button>
              </div>
              <p className="entrance-hint">If you cannot access this email, contact the Registrar for identity-checked account recovery.</p>
            </form> : step === 'password' && challenge ? <form noValidate onSubmit={completePasswordSetup} className="account-onboarding__password-setup">
              <h4>Create your portal password</h4>
              <p>Student Number <strong>{studentId}</strong></p>
              <label htmlFor="student-new-password">New Password</label>
              <PasswordInput id="student-new-password" ref={passwordField} visible={passwordVisible}
                onToggle={() => setPasswordVisible(!passwordVisible)} autoComplete="new-password"
                minLength={12} maxLength={128} required disabled={busy} value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)} />
              <label htmlFor="student-confirm-password">Confirm Password</label>
              <PasswordInput id="student-confirm-password" visible={passwordVisible} autoComplete="new-password"
                minLength={12} maxLength={128} required disabled={busy} value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)} />
              <PasswordStrengthChecklist password={newPassword} confirmPassword={confirmPassword} />
              <p className="entrance-hint">Your password stays with your ClassSync account.</p>
              <TurnstileWidget key={turnstileRevision} onToken={onTurnstileToken} />
              <Button type="submit" disabled={busy}>{busy ? 'Securing your account…' : 'Create portal password'}</Button>
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
            variant="ghost"
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
