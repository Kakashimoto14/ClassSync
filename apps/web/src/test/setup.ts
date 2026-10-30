import { afterEach, vi } from 'vitest';

// Pure logic suites use Node; only DOM suites need matchers and React teardown.
if (typeof window !== 'undefined') {
  await import('@testing-library/jest-dom/vitest');
  const { cleanup } = await import('@testing-library/react');
  // jsdom has no layout/scrolling implementation; browser QA checks positioning.
  window.scrollTo = vi.fn();
  // Vitest globals are disabled, so Testing Library cannot register automatic cleanup.
  afterEach(cleanup);
}
