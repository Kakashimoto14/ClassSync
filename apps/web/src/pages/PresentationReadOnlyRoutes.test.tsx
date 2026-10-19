import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { routeDefinitions } from '../routes/route-config';
import { ProductScreenPage } from './ProductScreenPage';
import { rememberWorkspace } from '../lib/workspace-context';
vi.mock('../lib/presentation-sample', async (original) => ({
  ...(await original<typeof import('../lib/presentation-sample')>()),
  presentationOnlyBuild: true,
}));
vi.mock('../components/layout/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}));
vi.mock('./ScheduledRooms', () => ({ ScheduledRooms: () => null }));
afterEach(() => vi.unstubAllGlobals());
it.each([
  '/admin/ai-scheduling',
  '/admin/schedule-manager',
  '/admin/schedule-manager/drafts',
  '/admin/academic',
  '/admin/conflicts',
])('keeps the public presentation route %s read-only without API access', (path) => {
  const fetcher = vi.fn();
  vi.stubGlobal('fetch', fetcher);
  const definition = routeDefinitions.find((route) => route.path === path);
  expect(definition).toBeDefined();
  render(
    <MemoryRouter>
      <ProductScreenPage definition={definition!} />
    </MemoryRouter>,
  );
  expect(screen.getByRole('heading', { name: 'Read-only presentation' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Review sample timetable' })).toHaveAttribute(
    'href',
    '/admin/calendar',
  );
  expect(
    screen.queryByRole('button', { name: /Generate|Save|Publish|Import/ }),
  ).not.toBeInTheDocument();
  expect(fetcher).not.toHaveBeenCalled();
});

it.each(['teacher', 'administrator'] as const)(
  'preserves the %s presentation context on room availability',
  (role) => {
    sessionStorage.clear();
    rememberWorkspace(role, {
      period: 'classsync-presentation-v1',
      identity: '',
      draft: '',
      mode: 'presentation',
      date: '2026-10-19',
    });
    const fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    const definition = routeDefinitions.find(
      (route) => route.role === role && route.roomMode === 'availability',
    );
    render(
      <MemoryRouter>
        <ProductScreenPage definition={definition!} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Live room occupancy is unavailable/)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Check published occupancy/ }),
    ).not.toBeInTheDocument();
    expect(fetcher).not.toHaveBeenCalled();
    sessionStorage.clear();
  },
);
