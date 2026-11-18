// @vitest-environment node
import { beforeEach, expect, it, vi } from 'vitest';
import { accountRequest, createStudentAccount, recoverPassword } from './account-actions';

const fixture = vi.hoisted(() => ({
  auth: { currentUser: null as null | { uid: string; getIdToken: ReturnType<typeof vi.fn> } },
  signup: vi.fn(),
  google: vi.fn(),
  googleProvider: vi.fn(),
  verify: vi.fn(),
  reset: vi.fn(),
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

it('does not disclose an unknown account through password recovery', async () => {
  fixture.reset.mockRejectedValue({ code: 'auth/user-not-found' });
  await expect(recoverPassword('unknown@synthetic.invalid')).resolves.toBeUndefined();
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
