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
}
export type UniversitySession =
  | { status: 'checking' | 'signed-out' | 'role-required' | 'denied' | 'unavailable' | 'offline' }
  | { status: 'authorized'; membership: UniversityMembership };
export type SessionIssue = 'role-required' | 'denied' | 'unavailable' | 'offline';
export class UniversitySessionError extends Error {
  constructor(public readonly issue: SessionIssue) {
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

/** In-memory authority only. Every check discards prior membership first. */
export function createUniversitySession(
  driver: UniversitySessionDriver,
  changed: (state: UniversitySession) => void,
  timeoutMs = 10_000,
) {
  let user: UniversityIdentity | null = null;
  let selected: UserRole | undefined;
  let generation = 0;
  let disposed = false;
  let logoutBlocked = false;
  let offline = false;
  let abort: AbortController | undefined;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  const emit = (state: UniversitySession) => {
    if (!disposed) changed(state);
  };
  const cancel = () => {
    generation++;
    abort?.abort();
    clearTimeout(timeout);
  };
  const refresh = async (role = selected) => {
    if (disposed) return;
    if (logoutBlocked) {
      emit({ status: 'unavailable' });
      return;
    }
    if (!user) {
      emit({ status: 'signed-out' });
      return;
    }
    if (offline) {
      emit({ status: 'offline' });
      return;
    }
    cancel();
    selected = role;
    const current = generation;
    const identity = user;
    const request = new AbortController();
    abort = request;
    emit({ status: 'checking' });
    timeout = setTimeout(() => {
      if (current !== generation || disposed) return;
      generation++;
      request.abort();
      emit({ status: 'unavailable' });
    }, timeoutMs);
    try {
      const result = await driver.lookup(identity, role, request.signal);
      const membership = parseUniversityMembership({ data: result }, identity.uid, role);
      if (current === generation && !disposed) emit({ status: 'authorized', membership });
    } catch (error) {
      if (current === generation && !disposed)
        emit({ status: error instanceof UniversitySessionError ? error.issue : 'unavailable' });
    } finally {
      if (current === generation) clearTimeout(timeout);
    }
  };
  const unsubscribe = driver.observe(
    (next) => {
      if (disposed || logoutBlocked) return;
      if (next?.uid !== user?.uid) selected = undefined;
      cancel();
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
      void refresh(role);
    },
    offline: () => {
      offline = true;
      cancel();
      emit({ status: 'offline' });
    },
    online: (role?: UserRole) => {
      offline = false;
      void refresh(role);
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
      unsubscribe();
    },
  };
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
  return {
    uid: value.uid,
    tenant_id: value.tenant_id,
    role: value.role,
    membership_revision: value.membership_revision,
    ...(value.role === 'student' ? { student_id: value.student_id } : {}),
    ...(value.role === 'teacher' ? { faculty_id: value.faculty_id } : {}),
  };
}
