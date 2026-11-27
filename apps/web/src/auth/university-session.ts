import type { UserRole } from '../types/ui';

export interface UniversityIdentity {
  uid: string;
  getIdToken: () => Promise<string>;
}
export interface UniversityMembership {
  uid: string;
  tenant_id: string;
  role: UserRole;
  membership_revision: number;
  student_id?: string;
  faculty_id?: string;
  available_roles?: UserRole[];
}
export type UniversitySession =
  | { status: 'checking'; waking?: boolean }
  | {
      status:
        | 'signed-out'
        | 'verification-required'
        | 'expired'
        | 'denied'
        | 'unavailable'
        | 'offline';
    }
  | { status: 'role-required'; availableRoles?: UserRole[] }
  | { status: 'authorized'; membership: UniversityMembership };
export type SessionIssue =
  'role-required' | 'verification-required' | 'expired' | 'denied' | 'unavailable' | 'offline';
export class UniversitySessionError extends Error {
  constructor(
    public readonly issue: SessionIssue,
    public readonly availableRoles?: UserRole[],
    /** A cold start, gateway restart or network blip that may succeed shortly. */
    public readonly retryable = false,
  ) {
    super(issue);
  }
}
export interface UniversitySessionDriver {
  observe: (next: (user: UniversityIdentity | null) => void, error: () => void) => () => void;
  lookup: (
    user: UniversityIdentity,
    role: UserRole | undefined,
    signal: AbortSignal,
  ) => Promise<UniversityMembership>;
  signOut: () => Promise<void>;
}

/**
 * In-memory authority only. A first check, a user change or a role change discards prior
 * membership before asking. Re-checking the same granted membership is silent: only a
 * confirmed server answer revokes it, and every API call is still authorized server-side.
 */
export function createUniversitySession(
  driver: UniversitySessionDriver,
  changed: (state: UniversitySession) => void,
  timeoutMs = 10_000,
  { retryDelaysMs = [1500, 4000], cooldownMs = 60_000 } = {},
) {
  let user: UniversityIdentity | null = null;
  let selected: UserRole | undefined;
  let granted: UniversityMembership | undefined;
  let verifiedAt = 0;
  let generation = 0;
  let disposed = false;
  let logoutBlocked = false;
  let offline = false;
  let busy = false;
  let abort: AbortController | undefined;
  let requestUid: string | undefined;
  let requestRole: UserRole | undefined;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  const emit = (state: UniversitySession) => {
    granted = state.status === 'authorized' ? state.membership : undefined;
    if (!disposed) changed(state);
  };
  const cancel = () => {
    generation++;
    abort?.abort();
    abort = undefined;
    busy = false;
    requestUid = undefined;
    requestRole = undefined;
    clearTimeout(timeout);
  };
  /** Bounds token and lookup work even when the underlying promise never settles. */
  const lookup = (identity: UniversityIdentity, role: UserRole | undefined) => {
    const request = new AbortController();
    abort = request;
    return new Promise<UniversityMembership>((resolve, reject) => {
      const timer = setTimeout(() => {
        request.abort();
        reject(new UniversitySessionError('unavailable', undefined, true));
      }, timeoutMs);
      request.signal.addEventListener('abort', () => clearTimeout(timer), { once: true });
      driver.lookup(identity, role, request.signal).then(
        (value) => {
          clearTimeout(timer);
          resolve(value);
        },
        (error: unknown) => {
          clearTimeout(timer);
          reject(error);
        },
      );
    });
  };
  const refresh = async (role = selected, force = false) => {
    if (disposed) return;
    if (logoutBlocked) {
      emit({ status: 'unavailable' });
      return;
    }
    if (!user) {
      emit({ status: 'signed-out' });
      return;
    }
    const quiet = granted?.uid === user.uid && (role === undefined || role === granted.role);
    if (offline) {
      if (!quiet) emit({ status: 'offline' });
      return;
    }
    if (quiet && !force && Date.now() - verifiedAt < cooldownMs) return;
    if (busy && requestUid === user.uid && requestRole === role) return;
    cancel();
    selected = role;
    const current = generation;
    const stale = () => current !== generation || disposed;
    const identity = user;
    busy = true;
    requestUid = identity.uid;
    requestRole = role;
    if (!quiet) emit({ status: 'checking' });
    for (let attempt = 0; ; attempt++) {
      try {
        const result = await lookup(identity, role);
        if (stale()) return;
        const membership = parseUniversityMembership({ data: result }, identity.uid, role);
        verifiedAt = Date.now();
        if (!quiet || JSON.stringify(membership) !== JSON.stringify(granted))
          emit({ status: 'authorized', membership });
      } catch (error) {
        if (stale()) return;
        const known = error instanceof UniversitySessionError ? error : undefined;
        if (known?.retryable && attempt < retryDelaysMs.length) {
          if (!quiet) emit({ status: 'checking', waking: true });
          await new Promise((resolve) => {
            timeout = setTimeout(resolve, retryDelaysMs[attempt]);
          });
          if (stale()) return;
          continue;
        }
        const status = known?.issue ?? 'unavailable';
        // A transient failure is not a denial: keep the verified workspace on screen.
        if (!quiet || (status !== 'unavailable' && status !== 'offline')) {
          if (status === 'denied') selected = undefined;
          if (status === 'role-required') {
            const availableRoles = known?.availableRoles;
            emit({ status, ...(availableRoles ? { availableRoles } : {}) });
          } else emit({ status });
        }
      }
      break;
    }
    busy = false;
    abort = undefined;
    requestUid = undefined;
    requestRole = undefined;
  };
  const unsubscribe = driver.observe(
    (next) => {
      if (disposed || logoutBlocked) return;
      // Hourly token refreshes re-announce the same user and must not disturb the workspace.
      if (next && granted && next.uid === user?.uid) {
        user = next;
        void refresh();
        return;
      }
      if (next?.uid !== user?.uid) selected = undefined;
      cancel();
      granted = undefined;
      user = next;
      if (!next) emit({ status: 'signed-out' });
      else void refresh();
    },
    () => {
      if (disposed || logoutBlocked) return;
      cancel();
      user = null;
      emit({ status: 'unavailable' });
    },
  );
  return {
    refresh: (role?: UserRole) => {
      void refresh(role, true);
    },
    offline: () => {
      offline = true;
      cancel();
      if (!granted) emit({ status: 'offline' });
    },
    online: (role?: UserRole, force = false) => {
      const resumed = offline;
      offline = false;
      void refresh(role, force || resumed);
    },
    signOut: async () => {
      if (disposed) return;
      logoutBlocked = true;
      cancel();
      user = null;
      selected = undefined;
      const current = generation;
      emit({ status: 'checking' });
      timeout = setTimeout(() => {
        if (current === generation && !disposed) {
          generation++;
          emit({ status: 'unavailable' });
        }
      }, timeoutMs);
      try {
        await driver.signOut();
        if (disposed || current !== generation) return;
        logoutBlocked = false;
        emit({ status: 'signed-out' });
      } catch {
        if (current === generation) emit({ status: 'unavailable' });
      } finally {
        if (current === generation) clearTimeout(timeout);
      }
    },
    dispose: () => {
      if (disposed) return;
      disposed = true;
      cancel();
      user = null;
      granted = undefined;
      unsubscribe();
    },
  };
}

export function parseAvailableRoles(value: unknown): UserRole[] {
  const roles: UserRole[] = ['student', 'teacher', 'administrator'];
  return Array.isArray(value) ? roles.filter((role) => value.includes(role)) : [];
}

function nonblank(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}
export function parseUniversityMembership(
  payload: unknown,
  uid: string,
  selected?: UserRole,
): UniversityMembership {
  const value = (payload as { data?: UniversityMembership } | null)?.data;
  if (
    !value ||
    !nonblank(uid) ||
    value.uid !== uid ||
    !nonblank(value.tenant_id) ||
    !['student', 'teacher', 'administrator'].includes(value.role) ||
    (selected !== undefined && value.role !== selected) ||
    !Number.isSafeInteger(value.membership_revision) ||
    value.membership_revision < 1 ||
    (value.role === 'student' && !nonblank(value.student_id)) ||
    (value.role === 'teacher' && !nonblank(value.faculty_id))
  ) {
    throw new UniversitySessionError('unavailable');
  }
  const availableRoles = parseAvailableRoles(value.available_roles);
  return {
    ...(availableRoles.length > 1 && availableRoles.includes(value.role)
      ? { available_roles: availableRoles }
      : {}),
    uid: value.uid,
    tenant_id: value.tenant_id,
    role: value.role,
    membership_revision: value.membership_revision,
    ...(value.role === 'student' ? { student_id: value.student_id } : {}),
    ...(value.role === 'teacher' ? { faculty_id: value.faculty_id } : {}),
  };
}
