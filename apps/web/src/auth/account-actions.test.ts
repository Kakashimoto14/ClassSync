// @vitest-environment node
import { beforeEach, expect, it, vi } from 'vitest';
import { accountRequest, createStudentAccount, recoverPassword } from './account-actions';

const fixture = vi.hoisted(() => ({
  auth: { currentUser: null as null | {
    uid: string; getIdToken: ReturnType<typeof vi.fn>; email?: string;
    providerData?: Array<{ providerId: string }>;
  } },
  signup: vi.fn(),
  google: vi.fn(),
  googleProvider: vi.fn(),
  verify: vi.fn(),
  reset: vi.fn(),
  passwordSignIn: vi.fn(),
  customTokenSignIn: vi.fn(),
  linkCredential: vi.fn(),
  updatePassword: vi.fn(),
  verifyResetCode: vi.fn(),
  confirmReset: vi.fn(),
}));
vi.mock('../config/runtime-config', () => ({ appMode: 'institutional' }));
vi.mock('../lib/firebase', () => ({ firebaseApp: {} }));
vi.mock('./university-session-driver', () => ({
  identityEndpoint: (path: string) => '/api/v1' + path,
}));
vi.mock('firebase/auth', () => ({
  getAuth: () => fixture.auth,
  createUserWithEmailAndPassword: fixture.signup,
  GoogleAuthProvider: fixture.googleProvider,
  signInWithPopup: fixture.google,
  sendEmailVerification: fixture.verify,
  sendPasswordResetEmail: fixture.reset,
  verifyPasswordResetCode: fixture.verifyResetCode,
  confirmPasswordReset: fixture.confirmReset,
  signInWithEmailAndPassword: fixture.passwordSignIn,
  signInWithCustomToken: fixture.customTokenSignIn,
  EmailAuthProvider: { credential: (email: string, password: string) => ({ email, password }) },
  linkWithCredential: fixture.linkCredential,
  updatePassword: fixture.updatePassword,
}));
beforeEach(() => {
  vi.clearAllMocks();
  fixture.auth.currentUser = null;
});

it('creates a Firebase account then requests verification without any role API call', async () => {
  const user = { uid: 'synthetic', getIdToken: vi.fn() };
  fixture.signup.mockResolvedValue({ user });
  fixture.verify.mockResolvedValue(undefined);
  const fetch = vi.spyOn(globalThis, 'fetch');
  await createStudentAccount(' student@synthetic.invalid ', 'Synthetic-password-42!');
  expect(fixture.signup).toHaveBeenCalledWith(
    fixture.auth,
    'student@synthetic.invalid',
    'Synthetic-password-42!',
  );
  expect(fixture.verify).toHaveBeenCalledWith(user);
  expect(fetch).not.toHaveBeenCalled();
  fetch.mockRestore();
});

it('starts Google sign-in through Firebase and does not create a client-selected role', async () => {
  const provider = { setCustomParameters: vi.fn() };
  fixture.googleProvider.mockImplementation(function () {
    return provider;
  });
  fixture.google.mockResolvedValue({ user: { uid: 'google-student' } });

  await expect(import('./account-actions').then(({ signInWithGoogle }) => signInWithGoogle()))
    .resolves.toEqual({ user: { uid: 'google-student' } });

  expect(fixture.googleProvider).toHaveBeenCalledOnce();
  expect(provider.setCustomParameters).toHaveBeenCalledWith({ prompt: 'select_account' });
  expect(fixture.google).toHaveBeenCalledWith(fixture.auth, provider);
});

it('requests password recovery through the Gateway once with its Turnstile token', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => ({ data: { accepted: true } }),
  } as unknown as Response);
  await expect(recoverPassword('juan.delacruz@student.pnm.edu.ph', 'one-use-token'))
    .resolves.toBeUndefined();
  expect(fetch).toHaveBeenCalledOnce();
  expect(fetch).toHaveBeenCalledWith('/api/v1/auth/request-password-reset', expect.objectContaining({
    method: 'POST',
    signal: expect.any(AbortSignal),
    credentials: 'omit',
    cache: 'no-store',
    body: JSON.stringify({
      email: 'juan.delacruz@student.pnm.edu.ph', turnstile_token: 'one-use-token',
    }),
  }));
  expect(fixture.reset).not.toHaveBeenCalled();
  fetch.mockRestore();
});

it('verifies a reset action code and only submits passwords meeting the portal minimum', async () => {
  fixture.verifyResetCode.mockResolvedValue('juan.delacruz@student.pnm.edu.ph');
  fixture.confirmReset.mockResolvedValue(undefined);
  const { verifyPasswordResetCode, completePasswordReset } = await import('./account-actions');
  await verifyPasswordResetCode('opaque-action-code');
  await expect(completePasswordReset('opaque-action-code', 'Short-1!')).rejects.toThrow(
    'Choose a password that meets all requirements.',
  );
  await completePasswordReset('opaque-action-code', 'Campus-password-26!');
  expect(fixture.verifyResetCode).toHaveBeenCalledWith(fixture.auth, 'opaque-action-code');
  expect(fixture.confirmReset).toHaveBeenCalledWith(
    fixture.auth,
    'opaque-action-code',
    'Campus-password-26!',
  );
});

it('exchanges a student number and Turnstile token for a Firebase custom-token session', async () => {
  fixture.auth.currentUser = null;
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => ({ data: { custom_token: 'firebase-custom-token' } }),
  } as unknown as Response);
  const { signInToAccount } = await import('./account-actions');

  await signInToAccount('23-01425', 'campus-pass-2026', 'turnstile-token');

  expect(fetch).toHaveBeenCalledWith('/api/v1/auth/student-password-login', expect.objectContaining({
    method: 'POST', credentials: 'omit', cache: 'no-store',
    body: JSON.stringify({
      student_id: '23-01425', password: 'campus-pass-2026', turnstile_token: 'turnstile-token',
    }),
  }));
  expect(fixture.customTokenSignIn).toHaveBeenCalledWith(fixture.auth, 'firebase-custom-token');
  fetch.mockRestore();
});

it('links a password provider to a recently authenticated first-time Google account', async () => {
  const user = {
    uid: 'student-a', email: 'juan.delacruz@student.pnm.edu.ph',
    providerData: [{ providerId: 'google.com' }], getIdToken: vi.fn(),
  };
  fixture.auth.currentUser = user;
  fixture.linkCredential.mockResolvedValue(undefined);
  const { setStudentPortalPassword } = await import('./account-actions');

  await setStudentPortalPassword('campus-pass-2026', 'student-a');

  expect(fixture.linkCredential).toHaveBeenCalledWith(user, {
    email: 'juan.delacruz@student.pnm.edu.ph', password: 'campus-pass-2026',
  });
});

it('does not send a mutation when the account changes during token acquisition', async () => {
  let complete!: (value: string) => void;
  fixture.auth.currentUser = {
    uid: 'previous',
    getIdToken: vi.fn(
      () =>
        new Promise<string>((resolve) => {
          complete = resolve;
        }),
    ),
  };
  const fetch = vi.spyOn(globalThis, 'fetch');
  const pending = accountRequest('student-claims', 'POST', { student_id: 'synthetic' });
  await vi.waitFor(() => expect(fixture.auth.currentUser?.getIdToken).toHaveBeenCalled());
  fixture.auth.currentUser = null;
  complete('synthetic-token');
  await expect(pending).rejects.toThrow('Sign in to continue');
  expect(fetch).not.toHaveBeenCalled();
  fetch.mockRestore();
});

it('rejects a late private response after the user changes while parsing', async () => {
  fixture.auth.currentUser = {
    uid: 'previous',
    getIdToken: vi.fn().mockResolvedValue('synthetic-token'),
  };
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: true,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => {
      fixture.auth.currentUser = null;
      return { data: 'private' };
    },
  } as unknown as Response);
  await expect(accountRequest('onboarding')).rejects.toThrow('Sign in to continue');
  fetch.mockRestore();
});

it('bounds token acquisition and does not send a timed-out mutation', async () => {
  vi.useFakeTimers();
  try {
    fixture.auth.currentUser = { uid: 'synthetic', getIdToken: vi.fn(() => new Promise(() => {})) };
    const fetch = vi.spyOn(globalThis, 'fetch');
    const result = expect(accountRequest('student-claims', 'POST', {})).rejects.toThrow(
      'timed out',
    );
    await vi.advanceTimersByTimeAsync(10_001);
    await result;
    expect(fetch).not.toHaveBeenCalled();
    fetch.mockRestore();
  } finally {
    vi.useRealTimers();
  }
});

it('replaces raw database diagnostics in account service responses with a safe message', async () => {
  fixture.auth.currentUser = { uid: 'synthetic', getIdToken: vi.fn().mockResolvedValue('token') };
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: false,
    status: 500,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => ({ error: { message: 'relation classsync_identity.memberships does not exist' } }),
  } as unknown as Response);
  await expect(accountRequest('onboarding')).rejects.toThrow(
    'Account service unavailable. Please try again later.',
  );
  fetch.mockRestore();
});
