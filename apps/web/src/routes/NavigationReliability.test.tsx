import { act, fireEvent, render, screen } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { appRoutes } from './app-routes';
import { dashboardPath } from './route-config';
import { previewSessionKey } from '../auth/preview-session';
import type { UserRole } from '../types/ui';

beforeEach(() => {
  sessionStorage.clear();
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
});

function open(path = '/dev/role-preview') {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] });
  const view = render(<RouterProvider router={router} />);
  return { router, view };
}
async function choose(role: UserRole) {
  const result = open();
  fireEvent.click(screen.getByRole('button', { name: `Open ${role} demo` }));
  await act(async () => {});
  expect(result.router.state.location.pathname).toBe(dashboardPath(role));
  return result;
}
function expectRole(role: UserRole) {
  expect(JSON.parse(sessionStorage.getItem(previewSessionKey)!).role).toBe(role);
  expect(screen.queryByRole('heading', { name: 'Choose your workspace' })).not.toBeInTheDocument();
  expect(
    screen.queryByRole('heading', { name: 'Your campus, coordinated.' }),
  ).not.toBeInTheDocument();
}

describe('real route tree preview continuity', () => {
  it.each([
    ['student', ['/student/schedule', '/student/rooms', '/student/rooms/detail?id=cdm-prrc-302']],
    ['teacher', ['/teacher/schedule', '/teacher/change-requests/detail?id=request-room-access']],
    [
      'administrator',
      ['/admin/conflicts/detail?id=conflict-science-overlap', '/admin/rooms', '/admin/dashboard'],
    ],
  ] as const)(
    '%s keeps selection through navigation, back, forward, and refresh',
    async (role, paths) => {
      const { router, view } = await choose(role);
      // Dashboard refresh must restore before a route guard can redirect.
      view.unmount();
      router.dispose();
      const restored = open(dashboardPath(role));
      expectRole(role);
      for (const path of paths) {
        await act(() => restored.router.navigate(path));
        expect(
          restored.router.state.location.pathname + restored.router.state.location.search,
        ).toBe(path);
        expectRole(role);
      }
      await act(() => restored.router.navigate(-1));
      expectRole(role);
      await act(() => restored.router.navigate(1));
      expectRole(role);
      const nested = paths.find((path) => path.includes('/detail'))!;
      await act(() => restored.router.navigate(nested));
      restored.view.unmount();
      restored.router.dispose();
      const detail = open(nested);
      expect(detail.router.state.location.pathname + detail.router.state.location.search).toBe(
        nested,
      );
      expectRole(role);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(role === 'student' ? 'PRRC 302' : /Details/);
    },
    15000,
  );

  it('retains the selected role on forbidden navigation and recovers to its workspace', async () => {
    const { router } = await choose('student');
    await act(() => router.navigate('/admin/dashboard'));
    expect(router.state.location.pathname).toBe('/forbidden');
    expectRole('student');
    fireEvent.click(screen.getByRole('link', { name: 'Return to your dashboard' }));
    await act(async () => {});
    expect(router.state.location.pathname).toBe('/student/dashboard');
  });

  it('switches roles only through explicit selection and exit prevents history revival', async () => {
    const { router, view } = await choose('student');
    await act(() => router.navigate('/dev/role-preview'));
    fireEvent.click(screen.getByRole('button', { name: 'Open teacher demo' }));
    await act(async () => {});
    expect(router.state.location.pathname).toBe('/teacher/dashboard');
    expectRole('teacher');
    fireEvent.click(screen.getAllByRole('button', { name: 'Exit demo' })[0]);
    await act(async () => {});
    expect(router.state.location.pathname).toBe('/auth/login');
    expect(sessionStorage.getItem(previewSessionKey)).toBeNull();
    await act(() => router.navigate(-1));
    expect(screen.queryByRole('heading', { name: 'Your day' })).not.toBeInTheDocument();
    view.unmount();
    router.dispose();
    const revisit = open('/teacher/dashboard');
    expect(revisit.router.state.location.pathname).toBe('/auth/login');
  });

  it('preserves a valid direct link with query and hash after explicit matching selection', async () => {
    const path = '/teacher/change-requests/detail/?id=request-room-access#record';
    const { router } = open(path);
    expect(router.state.location.pathname).toBe('/auth/login');
    fireEvent.click(screen.getByRole('link', { name: 'Explore ClassSync' }));
    await act(async () => {});
    fireEvent.click(screen.getByRole('button', { name: 'Open teacher demo' }));
    await act(async () => {});
    expect(
      router.state.location.pathname + router.state.location.search + router.state.location.hash,
    ).toBe(path);
    expectRole('teacher');
  });
});
