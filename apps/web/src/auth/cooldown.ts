export class RateLimitError extends Error {
  readonly retryAfterSeconds: number;

  constructor(message: string, retryAfterSeconds: number) {
    super(message);
    this.name = 'RateLimitError';
    this.retryAfterSeconds = Math.max(1, Math.min(3600, Math.ceil(retryAfterSeconds)));
  }
}

function key(action: string, identity: string) {
  return `classsync.cooldown.${action}.${identity.trim().toLowerCase()}`;
}

export function startCooldown(action: string, identity: string, seconds = 30): number {
  const expiresAt = Date.now() + Math.max(1, seconds) * 1000;
  try {
    sessionStorage.setItem(key(action, identity), String(expiresAt));
  } catch {
    // The live timer still works when storage is disabled.
  }
  return seconds;
}

export function cooldownRemaining(action: string, identity: string): number {
  try {
    const expiresAt = Number(sessionStorage.getItem(key(action, identity)));
    const seconds = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
    if (!seconds) sessionStorage.removeItem(key(action, identity));
    return seconds;
  } catch {
    return 0;
  }
}

export function retryAfterFrom(error: unknown): number | null {
  return error instanceof RateLimitError ? error.retryAfterSeconds : null;
}
