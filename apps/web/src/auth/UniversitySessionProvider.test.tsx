import { StrictMode } from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, expect, it, vi } from 'vitest';
import { UniversitySessionProvider } from './UniversitySessionProvider';
import { useUniversitySession } from './university-session-context';
import type { UniversityIdentity, UniversitySessionDriver } from './university-session';

const source = vi.hoisted(() => ({ mode: 'institutional', load: vi.fn() }));
vi.mock('../config/runtime-config', () => ({
  get appMode() {
    return source.mode;
  },
}));
vi.mock('./university-session-driver', () => ({ loadUniversitySessionDriver: source.load }));
function Status() {
  const { state } = useUniversitySession();
  return <p>{state.status}</p>;
}
beforeEach(() => {
  vi.clearAllMocks();
  source.mode = 'institutional';
});

it.each(['presentation', 'sandbox'])('does not mount university identity in %s mode', (mode) => {
  source.mode = mode;
  render(
    <UniversitySessionProvider>
      <Status />
    </UniversitySessionProvider>,
  );
  expect(source.load).not.toHaveBeenCalled();
});
it('cleans StrictMode observers, clears old data and never revives after unmount', async () => {
  let next!: (identity: UniversityIdentity | null) => void;
  const unsubscribe = vi.fn();
  const driver: UniversitySessionDriver = {
    observe: vi.fn((listener) => {
      next = listener;
      return unsubscribe;
    }),
    lookup: vi
      .fn()
      .mockResolvedValue({
        uid: 'u',
        tenant_id: 't',
        role: 'student',
        student_id: 's',
        membership_revision: 1,
      }),
    signOut: vi.fn(),
  };
  source.load.mockResolvedValue(driver);
  const queryClient = new QueryClient();
  queryClient.setQueryData(['private'], 'old identity data');
  const view = render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <UniversitySessionProvider>
          <Status />
        </UniversitySessionProvider>
      </QueryClientProvider>
    </StrictMode>,
  );
  await waitFor(() => expect(driver.observe).toHaveBeenCalledOnce());
  expect(queryClient.getQueryData(['private'])).toBeUndefined();
  await act(async () => next({ uid: 'u', getIdToken: vi.fn() }));
  expect(screen.getByText('authorized')).toBeInTheDocument();
  queryClient.setQueryData(['private'], 'current identity data');
  act(() => next(null));
  expect(screen.getByText('signed-out')).toBeInTheDocument();
  expect(queryClient.getQueryData(['private'])).toBeUndefined();
  view.unmount();
  expect(unsubscribe).toHaveBeenCalledOnce();
  const calls = vi.mocked(driver.lookup).mock.calls.length;
  next({ uid: 'u', getIdToken: vi.fn() });
  expect(driver.lookup).toHaveBeenCalledTimes(calls);
});
it('does not attach an observer when asynchronous setup finishes after unmount', async () => {
  let resolve!: (driver: UniversitySessionDriver) => void;
  source.load.mockReturnValue(
    new Promise<UniversitySessionDriver>((done) => {
      resolve = done;
    }),
  );
  const queryClient = new QueryClient();
  const view = render(
    <QueryClientProvider client={queryClient}>
      <UniversitySessionProvider>
        <Status />
      </UniversitySessionProvider>
    </QueryClientProvider>,
  );
  view.unmount();
  const observe = vi.fn();
  await act(async () => resolve({ observe, lookup: vi.fn(), signOut: vi.fn() }));
  expect(observe).not.toHaveBeenCalled();
});
