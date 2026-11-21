import { appMode } from '../config/runtime-config';
import { firebaseApp } from '../lib/firebase';
import { identityEndpoint } from './university-session-driver';
import { RateLimitError } from './cooldown';
import { normalizeAccountEmail } from './student-number';
import * as firebaseAuthSdk from 'firebase/auth';
import { getAuth, GoogleAuthProvider, signInWithPopup, signInWithRedirect, getRedirectResult, type User } from 'firebase/auth';

const AUTH_TIMEOUT_MS = 45_000;
const GOOGLE_CHALLENGE_KEY = 'classsync.google.challenge';

async function fetchAuthWithRetry(input: RequestInfo | URL, init: RequestInit) {
  for (let attempt = 0; ; attempt += 1) {
    const response = await fetch(input, { ...init, signal: AbortSignal.timeout(AUTH_TIMEOUT_MS) });
    if (attempt === 0 && [502, 503, 504].includes(response.status)) {
      await new Promise((resolve) => globalThis.setTimeout(resolve, 800));
      continue;
    }
    return response;
  }
}

async function provider() {
  if (appMode !== 'institutional') throw new Error('University access is not connected.');
  if (!firebaseApp) throw new Error('University access is not connected.');
  return { auth: getAuth(firebaseApp), sdk: firebaseAuthSdk };
}

export async function signInToAccount(
  identifier: string,
  password: string,
  turnstileToken?: string,
) {
  const { auth, sdk } = await provider();
  if (/^[0-9]{2}-[0-9]{5}$/.test(identifier.trim())) {
    const response = await fetchAuthWithRetry(identityEndpoint('/auth/student-password-login'), {
      method: 'POST',
      credentials: 'omit',
      cache: 'no-store',
      redirect: 'error',
      referrerPolicy: 'no-referrer',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        student_id: identifier.trim(),
        password,
        turnstile_token: turnstileToken ?? '',
      }),
    });
    if (!response.headers.get('content-type')?.includes('application/json'))
      throw new Error('Invalid student number or password.');
    const payload = await response.json();
    if (!response.ok || typeof payload?.data?.custom_token !== 'string')
      throw new Error('Invalid student number or password.');
    await sdk.signInWithCustomToken(auth, payload.data.custom_token);
    return;
  }
  await sdk.signInWithEmailAndPassword(auth, normalizeAccountEmail(identifier), password);
}

export function signInWithGoogle(turnstileToken: string) {
  if (!turnstileToken) throw new Error('Complete the human verification check first.');
  if (appMode !== 'institutional' || !firebaseApp) throw new Error('University access is not connected.');
  const auth = getAuth(firebaseApp);
  const google = new GoogleAuthProvider();
  google.setCustomParameters({ prompt: 'select_account' });
  const redirectFallback = () => {
    sessionStorage.setItem(GOOGLE_CHALLENGE_KEY, JSON.stringify({ token: turnstileToken, at: Date.now() }));
    return signInWithRedirect(auth, google).then(() => undefined);
  };
  try {
    return signInWithPopup(auth, google).catch((error: { code?: string }) => {
      if (error.code !== 'auth/popup-blocked') throw error;
      return redirectFallback();
    });
  } catch (error) {
    if ((error as { code?: string }).code !== 'auth/popup-blocked') throw error;
    return redirectFallback();
  }
}

export async function verifyGoogleSignIn(user: User, turnstileToken: string) {
  const token = await user.getIdToken();
  const response = await fetchAuthWithRetry(identityEndpoint('/auth/google-sign-in'), {
    method: 'POST', credentials: 'omit', cache: 'no-store', redirect: 'error', referrerPolicy: 'no-referrer',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ turnstile_token: turnstileToken }),
  });
  if (!response.ok) throw new Error('Unable to verify this sign-in. Please try again.');
}

export async function completeGoogleRedirectSignIn() {
  if (!firebaseApp || appMode !== 'institutional') return null;
  const raw = sessionStorage.getItem(GOOGLE_CHALLENGE_KEY);
  if (!raw) return null;
  sessionStorage.removeItem(GOOGLE_CHALLENGE_KEY);
  try {
    const pending = JSON.parse(raw) as { token?: string; at?: number };
    if (!pending.token || !pending.at || Date.now() - pending.at > 240_000) return null;
    const result = await getRedirectResult(getAuth(firebaseApp));
    if (!result) return null;
    await verifyGoogleSignIn(result.user, pending.token);
    return result;
  } catch {
    await firebaseAuthSdk.signOut(getAuth(firebaseApp)).catch(() => undefined);
    return null;
  }
}

export async function createStudentAccount(email: string, password: string) {
  const { auth, sdk } = await provider();
  const result = await sdk.createUserWithEmailAndPassword(auth, normalizeAccountEmail(email), password);
  await accountRequest('send-verification-email', 'POST', {}, AUTH_TIMEOUT_MS, result.user.uid);
}

export async function recoverPassword(email: string, turnstileToken: string) {
  if (!email.trim() || !turnstileToken)
    throw new Error('Complete the email and human verification check first.');
  const response = await fetchAuthWithRetry(identityEndpoint('/auth/request-password-reset'), {
    method: 'POST',
    credentials: 'omit',
    cache: 'no-store',
    redirect: 'error',
    referrerPolicy: 'no-referrer',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: normalizeAccountEmail(email), turnstile_token: turnstileToken }),
  });
  if (!response.headers.get('content-type')?.includes('application/json'))
    throw new Error('Password reset is temporarily unavailable. Try again later.');
  const payload = await response.json();
  if (!response.ok) throw emailRequestError(response, payload);
  if (payload?.data?.accepted !== true)
    throw new Error('Password reset is temporarily unavailable. Try again later.');
}

function emailRequestError(
  response: Response,
  payload: { error?: { code?: unknown; message?: unknown; retryAfterSeconds?: unknown }; detail?: unknown },
): Error {
  if (payload?.error?.code === 'rate_limited') {
    const retry = Number(payload.error.retryAfterSeconds ?? response.headers.get('Retry-After') ?? 30);
    return new RateLimitError(
      typeof payload.error.message === 'string'
        ? safeAccountServiceMessage(payload.error.message)
        : 'Please wait before requesting another email.',
      retry,
    );
  }
  const message = typeof payload.error?.message === 'string'
    ? payload.error.message
    : typeof payload.detail === 'string' ? payload.detail : undefined;
  return new Error(message ? safeAccountServiceMessage(message) : 'Account service unavailable. Please try again later.');
}

export async function verifyPasswordResetCode(code: string) {
  if (!code || code.length > 2048) throw new Error('This password reset link is invalid or expired.');
  const { auth, sdk } = await provider();
  try {
    await sdk.verifyPasswordResetCode(auth, code);
  } catch {
    throw new Error('This password reset link is invalid or expired.');
  }
}

export async function applyEmailVerificationCode(code: string) {
  if (!code || code.length > 2048) throw new Error('This verification link is invalid or expired.');
  const { auth, sdk } = await provider();
  try {
    await sdk.applyActionCode(auth, code);
    if (auth.currentUser) {
      await sdk.reload(auth.currentUser);
      await auth.currentUser.getIdToken(true);
    }
  } catch {
    throw new Error('This verification link is invalid or expired.');
  }
}

export async function completePasswordReset(code: string, password: string) {
  if (!code || code.length > 2048 || password.length < 12 || password.length > 128)
    throw new Error('Choose a password that meets all requirements.');
  try {
    const response = await fetchAuthWithRetry(identityEndpoint('/auth/complete-password-reset'), {
      method: 'POST', credentials: 'omit', cache: 'no-store', redirect: 'error', referrerPolicy: 'no-referrer',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ oob_code: code, password }),
    });
    if (!response.ok) throw new Error('Password reset failed');
  } catch {
    throw new Error('The password could not be changed. Request a new reset link and try again.');
  }
}

export async function verifyHumanChallenge(token: string) {
  if (!token) throw new Error('Complete the human verification check first.');
  const response = await fetchAuthWithRetry(identityEndpoint('/auth/verify-turnstile'), {
    method: 'POST',
    credentials: 'omit',
    cache: 'no-store',
    redirect: 'error',
    referrerPolicy: 'no-referrer',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  if (!response.ok) throw new Error('Human verification could not be confirmed. Try again.');
}

export async function resendVerification(expectedUid?: string) {
  await accountRequest('send-verification-email', 'POST', {}, AUTH_TIMEOUT_MS, expectedUid);
}

export async function refreshVerifiedAccount(expectedUid?: string) {
  const { auth, sdk } = await provider();
  const user = currentAccount(auth, expectedUid);
  await sdk.reload(user);
  if (auth.currentUser !== user) throw new Error('Your account changed. Sign in again.');
  await user.getIdToken(true);
}

function currentAccount(auth: import('firebase/auth').Auth, expectedUid?: string) {
  const user = auth.currentUser;
  if (!user) throw new Error('Sign in to continue.');
  if (expectedUid && user.uid !== expectedUid)
    throw new Error('Your account changed. Sign in again.');
  return user;
}

export function accountError(error: unknown) {
  const code = (error as { code?: string })?.code;
  if (code === 'auth/email-already-in-use')
    return 'This account cannot be created. Try signing in or resetting your password.';
  if (code === 'auth/weak-password' || code === 'auth/password-does-not-meet-requirements')
    return 'Choose a stronger password that meets the account requirements.';
  if (code === 'auth/too-many-requests') return 'Too many attempts. Wait a moment, then try again.';
  if (code === 'auth/invalid-email') return 'Enter a valid email address.';
  if (code === 'auth/operation-not-allowed')
    return 'Account creation is unavailable. Contact your university.';
  if (code === 'auth/popup-closed-by-user') return 'Sign-in was cancelled. You can try again.';
  if (code === 'auth/popup-blocked') return 'Allow the sign-in window, then try again.';
  return 'The request could not be confirmed. Check your connection and try again.';
}

function safeAccountServiceMessage(message: unknown) {
  if (typeof message !== 'string' || message.length > 240 || /[\r\n]/.test(message) ||
      message.trimStart().startsWith('{') || message.trimStart().startsWith('[') ||
      /https?:\/\/|neondb|classsync_[a-z0-9_]+|\b(database|table|schema|sql|traceback|stack trace|exception)\b/i.test(message))
    return 'Account service unavailable. Please try again later.';
  return message;
}

export interface OnboardingStatus {
  email_verified: boolean;
  claim_state: 'pending' | 'approved' | 'rejected' | null;
  membership_state: 'active' | 'inactive' | 'revoked' | null;
  status: string;
  verification_mode?: 'cor_or_roster' | 'strict_roster';
}

export async function observeAccount(next: (uid: string | null) => void) {
  const { auth, sdk } = await provider();
  return sdk.onAuthStateChanged(auth, (user) => next(user?.uid ?? null));
}

export interface AccountProfile {
  uid: string;
  name: string;
  email: string;
  emailVerified: boolean;
}
const profileOf = (user: import('firebase/auth').User): AccountProfile => ({
  uid: user.uid,
  name: user.displayName ?? '',
  email: user.email ?? '',
  emailVerified: user.emailVerified,
});
export async function observeAccountProfile(next: (profile: AccountProfile | null) => void) {
  const { auth, sdk } = await provider();
  return sdk.onAuthStateChanged(auth, (user) => next(user ? profileOf(user) : null));
}
export async function updateAccountName(
  name: string,
  expectedUid?: string,
): Promise<AccountProfile> {
  const { auth, sdk } = await provider();
  const user = currentAccount(auth, expectedUid);
  const displayName = name.trim();
  if (!displayName || displayName.length > 100)
    throw new Error('Enter a name of up to 100 characters.');
  await sdk.updateProfile(user, { displayName });
  if (auth.currentUser !== user) throw new Error('Your account changed. Sign in again.');
  return profileOf(user);
}

export async function accountRequest<T>(
  path: string,
  method = 'GET',
  body?: unknown,
  timeoutMs = AUTH_TIMEOUT_MS,
  expectedUid?: string,
): Promise<T> {
  const { auth } = await provider();
  const user = currentAccount(auth, expectedUid);
  let timeout: ReturnType<typeof setTimeout> | undefined;
  let token: string;
  try {
    token = await Promise.race([
      user.getIdToken(),
      new Promise<never>((_, reject) => {
        timeout = setTimeout(
          () => reject(new Error('Account service timed out. Retry safely.')),
          10_000,
        );
      }),
    ]);
  } finally {
    clearTimeout(timeout);
  }
  if (auth.currentUser !== user) throw new Error('Sign in to continue.');
  const request: RequestInit = {
    method,
    credentials: 'omit',
    cache: 'no-store',
    redirect: 'error',
    referrerPolicy: 'no-referrer',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': body instanceof Blob ? body.type : 'application/json',
    },
    ...(body === undefined ? {} : { body: body instanceof Blob ? body : JSON.stringify(body) }),
  };
  let response: Response | undefined;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    response = await fetch(identityEndpoint('/auth/' + path), {
      ...request,
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (attempt === 0 && [502, 503, 504].includes(response.status)) {
      await new Promise((resolve) => globalThis.setTimeout(resolve, 800));
      continue;
    }
    break;
  }
  if (!response) throw new Error('Account service unavailable.');
  if (auth.currentUser !== user) throw new Error('Sign in to continue.');
  if (response.status === 204 && response.ok) return undefined as T;
  if (!response.headers.get('content-type')?.includes('application/json'))
    throw new Error('Account service unavailable.');
  const payload = await response.json();
  if (auth.currentUser !== user) throw new Error('Sign in to continue.');
  if (!response.ok)
    throw emailRequestError(response, payload);
  return payload.data as T;
}
