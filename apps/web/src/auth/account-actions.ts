import { appMode } from '../config/runtime-config';
import { identityEndpoint } from './university-session-driver';

async function provider() {
  if (appMode !== 'institutional') throw new Error('University access is not connected.');
  const [{ firebaseApp }, sdk] = await Promise.all([
    import('../lib/firebase'),
    import('firebase/auth'),
  ]);
  if (!firebaseApp) throw new Error('University access is not connected.');
  return { auth: sdk.getAuth(firebaseApp), sdk };
}

export async function createStudentAccount(email: string, password: string) {
  const { auth, sdk } = await provider();
  const result = await sdk.createUserWithEmailAndPassword(auth, email.trim(), password);
  await sdk.sendEmailVerification(result.user);
}

export async function recoverPassword(email: string) {
  const { auth, sdk } = await provider();
  try {
    await sdk.sendPasswordResetEmail(auth, email.trim());
  } catch (error) {
    // Keep the same response for an unknown account, including projects where
    // enumeration protection has not yet been configured.
    if ((error as { code?: string }).code !== 'auth/user-not-found') throw error;
  }
}

export async function resendVerification() {
  const { auth, sdk } = await provider();
  if (!auth.currentUser) throw new Error('Sign in to continue.');
  await sdk.sendEmailVerification(auth.currentUser);
}

export async function refreshVerifiedAccount() {
  const { auth, sdk } = await provider();
  if (!auth.currentUser) throw new Error('Sign in to continue.');
  await sdk.reload(auth.currentUser);
  await auth.currentUser.getIdToken(true);
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
  return 'The request could not be confirmed. Check your connection and try again.';
}

export interface OnboardingStatus {
  email_verified: boolean;
  claim_state: 'pending' | 'approved' | 'rejected' | null;
  membership_state: 'active' | 'inactive' | 'revoked' | null;
  status: string;
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
export async function updateAccountName(name: string): Promise<AccountProfile> {
  const { auth, sdk } = await provider();
  const user = auth.currentUser;
  if (!user) throw new Error('Sign in to continue.');
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
  timeoutMs = 10_000,
): Promise<T> {
  const { auth } = await provider();
  const user = auth.currentUser;
  if (!user) throw new Error('Sign in to continue.');
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
  const response = await fetch(identityEndpoint('/auth/' + path), {
    method,
    signal: AbortSignal.timeout(timeoutMs),
    credentials: 'omit',
    cache: 'no-store',
    redirect: 'error',
    referrerPolicy: 'no-referrer',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': body instanceof Blob ? body.type : 'application/json',
    },
    ...(body === undefined ? {} : { body: body instanceof Blob ? body : JSON.stringify(body) }),
  });
  if (auth.currentUser !== user) throw new Error('Sign in to continue.');
  if (response.status === 204 && response.ok) return undefined as T;
  if (!response.headers.get('content-type')?.includes('application/json'))
    throw new Error('Account service unavailable.');
  const payload = await response.json();
  if (auth.currentUser !== user) throw new Error('Sign in to continue.');
  if (!response.ok)
    throw new Error(
      typeof payload?.error?.message === 'string'
        ? payload.error.message
        : 'Account request could not be confirmed.',
    );
  return payload.data as T;
}
