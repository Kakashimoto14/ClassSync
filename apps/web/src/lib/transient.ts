/** One short retry for idempotent reads that hit a cold start or gateway restart. */
export function transientFailure(message: string) {
  return Object.assign(new Error(message), { transient: true });
}

export async function retryTransientRead<T>(
  read: () => Promise<T>,
  signal?: AbortSignal,
  delayMs = 1500,
): Promise<T> {
  try {
    return await read();
  } catch (error) {
    const failure = error as { transient?: boolean; status?: number };
    const retryable =
      failure.transient ||
      error instanceof TypeError ||
      [502, 503, 504].includes(failure.status ?? 0);
    if (!retryable || signal?.aborted) throw error;
    await new Promise((resolve) => window.setTimeout(resolve, delayMs));
    if (signal?.aborted) throw new DOMException('Request cancelled', 'AbortError');
    return read();
  }
}
