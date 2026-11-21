import { afterEach, describe, expect, it, vi } from 'vitest';
import { cooldownRemaining, startCooldown } from './cooldown';

afterEach(() => {
  sessionStorage.clear();
  vi.useRealTimers();
});

describe('session cooldown persistence', () => {
  it('restores the remaining time after refresh and normalizes identity', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-21T00:00:00Z'));
    expect(startCooldown('reset', 'Student.Demo@gmail.com', 30)).toBe(30);
    vi.advanceTimersByTime(11_000);
    expect(cooldownRemaining('reset', 'student.demo@gmail.com')).toBe(19);
  });
});
