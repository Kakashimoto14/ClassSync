import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// jsdom has no layout or scrolling implementation; browser QA checks actual positioning.
window.scrollTo = vi.fn();

// Vitest globals are disabled, so Testing Library cannot register automatic cleanup.
afterEach(cleanup);
