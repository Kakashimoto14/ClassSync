// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  createUniversitySession,
  parseUniversityMembership,
  UniversitySessionError,
  type UniversityIdentity,
  type UniversityMembership,
  type UniversitySession,
  type UniversitySessionDriver,
} from './university-session';

const membership: UniversityMembership = {
  uid: 'uid-a',
  tenant_id: 'tenant-a',
  role: 'student',
  student_id: 'student-a',
  membership_revision: 1,
};
const identity = (uid = 'uid-a'): UniversityIdentity => ({
  uid,
  getIdToken: vi.fn().mockResolvedValue('opaque-token'),
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
async function settle() {
  await Promise.resolve();
  await Promise.resolve();
}
function setup() {
  let next!: (user: UniversityIdentity | null) => void;
  let failure!: () => void;
  const unsubscribe = vi.fn();
  const driver: UniversitySessionDriver = {
    observe: (listener, error) => {
      next = listener;
      failure = error;
      return unsubscribe;
    },
    lookup: vi.fn().mockResolvedValue(membership),
    signOut: vi.fn().mockResolvedValue(undefined),
  };
  const states: UniversitySession[] = [];
  const session = createUniversitySession(driver, (state) => states.push(state), 100);
  return { driver, states, session, next, failure, unsubscribe, last: () => states.at(-1) };
}
afterEach(() => vi.useRealTimers());

describe('current university session authority', () => {
  it('observes signed-out then verifies identity without decoding tokens', async () => {
    const value = setup();
    value.next(null);
    expect(value.last()).toEqual({ status: 'signed-out' });
    value.next(identity());
    expect(value.last()).toEqual({ status: 'checking' });
    await settle();
    expect(value.last()).toEqual({ status: 'authorized', membership });
    value.session.dispose();
    expect(value.unsubscribe).toHaveBeenCalledOnce();
  });
  it('clears membership before role verification and shows server role denial', async () => {
    const value = setup();
    value.next(identity());
    await settle();
    vi.mocked(value.driver.lookup).mockRejectedValueOnce(
      new UniversitySessionError('role-required'),
    );
    value.session.refresh();
    expect(value.last()).toEqual({ status: 'checking' });
    await settle();
    expect(value.last()).toEqual({ status: 'role-required' });
    vi.mocked(value.driver.lookup).mockRejectedValueOnce(new UniversitySessionError('denied'));
    value.session.refresh('administrator');
    await settle();
    expect(value.last()).toEqual({ status: 'denied' });
    value.session.dispose();
  });
  it('cannot revive the previous UID after a later identity callback', async () => {
    const value = setup();
    const old = deferred<UniversityMembership>();
    vi.mocked(value.driver.lookup).mockReturnValueOnce(old.promise);
    vi.mocked(value.driver.lookup).mockResolvedValueOnce({ ...membership, uid: 'uid-b' });
    value.next(identity());
    value.next(identity('uid-b'));
    await settle();
    old.resolve({ ...membership, membership_revision: 99 });
    await settle();
    expect(value.states.filter((state) => state.status === 'authorized')).toHaveLength(1);
    expect(value.last()).toEqual({
      status: 'authorized',
      membership: { ...membership, uid: 'uid-b' },
    });
    value.session.dispose();
  });
  it('blocks late authorization after offline, signout or disposal', async () => {
    for (const action of ['offline', 'signout', 'dispose'] as const) {
      const value = setup();
      const old = deferred<UniversityMembership>();
      vi.mocked(value.driver.lookup).mockReturnValueOnce(old.promise);
      value.next(identity());
      if (action === 'signout') await value.session.signOut();
      else value.session[action]();
      old.resolve(membership);
      await settle();
      expect(value.states.some((state) => state.status === 'authorized')).toBe(false);
      value.session.dispose();
    }
  });
  it('keeps logout failure cleared despite further SDK events or refresh', async () => {
    const value = setup();
    value.next(identity());
    await settle();
    vi.mocked(value.driver.signOut).mockRejectedValueOnce(new Error('private SDK failure'));
    await value.session.signOut();
    expect(value.last()).toEqual({ status: 'unavailable' });
    const count = vi.mocked(value.driver.lookup).mock.calls.length;
    value.next(identity());
    value.session.refresh();
    await settle();
    expect(vi.mocked(value.driver.lookup)).toHaveBeenCalledTimes(count);
    await value.session.signOut();
    expect(value.last()).toEqual({ status: 'signed-out' });
    value.session.dispose();
  });
  it('bounds stalled token/lookup work and ignores its late completion', async () => {
    vi.useFakeTimers();
    const value = setup();
    const old = deferred<UniversityMembership>();
    vi.mocked(value.driver.lookup).mockReturnValueOnce(old.promise);
    value.next(identity());
    await vi.advanceTimersByTimeAsync(100);
    expect(value.last()).toEqual({ status: 'unavailable' });
    expect(vi.mocked(value.driver.lookup).mock.calls[0][2].aborted).toBe(true);
    old.resolve(membership);
    await settle();
    expect(value.last()).toEqual({ status: 'unavailable' });
    value.session.dispose();
  });
  it('keeps offline events cleared until online revalidation succeeds', async () => {
    const value = setup();
    value.next(identity());
    await settle();
    value.session.offline();
    value.next(identity());
    await settle();
    expect(value.last()).toEqual({ status: 'offline' });
    value.session.online();
    expect(value.last()).toEqual({ status: 'checking' });
    await settle();
    expect(value.last()).toEqual({ status: 'authorized', membership });
    value.session.dispose();
  });
  it('clears current authority on SDK observer failure', async () => {
    const value = setup();
    value.next(identity());
    await settle();
    value.failure();
    expect(value.last()).toEqual({ status: 'unavailable' });
    value.session.dispose();
  });
});

describe('membership response contract', () => {
  it('keeps only the authorized role record and rejects client role mismatch', () => {
    expect(
      parseUniversityMembership({ data: { ...membership, faculty_id: 'extra' } }, 'uid-a'),
    ).toEqual(membership);
    expect(() => parseUniversityMembership({ data: membership }, 'uid-a', 'teacher')).toThrow(
      UniversitySessionError,
    );
  });
  it.each([
    null,
    {},
    { ...membership, uid: 'another' },
    { ...membership, tenant_id: '' },
    { ...membership, role: 'superadmin' },
    { ...membership, student_id: undefined },
    { ...membership, membership_revision: 0 },
    { ...membership, membership_revision: 1.1 },
    { ...membership, membership_revision: '1' },
  ])('rejects invalid or mismatched membership %j', (data) => {
    expect(() => parseUniversityMembership({ data }, 'uid-a')).toThrow(UniversitySessionError);
  });
});
