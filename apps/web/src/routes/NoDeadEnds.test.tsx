import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { UniversitySessionContext } from '../auth/university-session-context';
import { DevelopmentRoleContext } from '../auth/development-role-context';
import type { UniversitySession } from '../auth/university-session';
import type { UserRole } from '../types/ui';
import { RoleRoute } from './RouteGuard';
import { routeDefinitions, type RouteDefinition } from './route-config';

vi.mock('../config/runtime-config', async () => {
  const { capabilitiesFor } = await import('../config/app-mode');
  return { appMode: 'institutional', capabilities: capabilitiesFor('institutional') };
});
// Every service read stays pending: only which screen a route renders matters here.
// The recovery cases below switch the same reads to fail.
const reads = vi.hoisted(() => ({ fail: false }));
const pending = vi.hoisted(() => () =>
  reads.fail
    ? Promise.reject(new Error('Owned service failure'))
    : new Promise<never>(() => {}),
);
vi.mock('../lib/institutional-api', () => ({ institutionalRequest: pending }));
vi.mock('../lib/student-timetable-api', () => ({ studentTimetableRequest: pending }));
vi.mock('../lib/academic-api', async (original) => ({
  ...(await original<typeof import('../lib/academic-api')>()),
  listAcademicPeriods: pending,
}));
vi.mock('../lib/admin-operations-api', async (original) => ({
  ...(await original<typeof import('../lib/admin-operations-api')>()),
  listRestrictions: pending,
}));
vi.mock('../lib/scheduling-api', async (original) => ({
  ...(await original<typeof import('../lib/scheduling-api')>()),
  listSchedulingDrafts: pending,
}));
vi.mock('../lib/publication-api', async (original) => ({
  ...(await original<typeof import('../lib/publication-api')>()),
  timetableRequest: pending,
}));
vi.mock('../components/layout/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}));

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
});

function session(role: UserRole): UniversitySession {
  return {
    status: 'authorized',
    membership: {
      uid: `owned-${role}`,
      tenant_id: 'owned-tenant',
      role,
      membership_revision: 1,
      ...(role === 'student' ? { student_id: 'owned-student' } : {}),
      ...(role === 'teacher' ? { faculty_id: 'owned-faculty' } : {}),
    },
  };
}

function Location() {
  return <output data-testid="location">{useLocation().pathname}</output>;
}

function view(definition: RouteDefinition, path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <DevelopmentRoleContext.Provider
        value={{ role: null, startDemo: vi.fn(), signOut: vi.fn() }}
      >
        <UniversitySessionContext.Provider
          value={{
            available: true,
            state: session(definition.role),
            refresh: vi.fn(),
            signOut: vi.fn(),
          }}
        >
          <Routes>
            <Route path={definition.path} element={<RoleRoute definition={definition} />} />
            <Route path="*" element={<p>Redirect target</p>} />
          </Routes>
          <Location />
        </UniversitySessionContext.Provider>
      </DevelopmentRoleContext.Provider>
    </MemoryRouter>,
  );
}

const concrete = (path: string) => path.replace(/:[A-Za-z]+/g, 'owned-id');

describe.each(['administrator', 'teacher', 'student'] as const)('%s routes', (role) => {
  const definitions: RouteDefinition[] = routeDefinitions.filter((item) => item.role === role);

  it.each(definitions.map((item) => [item.path, item] as const))(
    '%s is not a dead end',
    async (_path, definition) => {
      const { container } = view(definition, concrete(definition.path));
      // Wait until the lazy route chunk has replaced the page loader.
      await waitFor(
        () => {
          expect(
            screen.queryByText(/Loading (your workspace|this page|class schedule)…/),
          ).not.toBeInTheDocument();
          // A workspace screen, or the one retired path that redirects.
          expect(
            container.querySelector('main') ?? screen.queryByText('Redirect target'),
          ).not.toBeNull();
        },
        { timeout: 15000 },
      );
      expect(container.textContent).not.toContain('This service is not connected');
      expect(container.textContent).not.toContain('University access unavailable');
    },
    20000,
  );
});

it('redirects the retired academic detail page to Sections', async () => {
  const definition = routeDefinitions.find((item) => item.path === '/admin/academic/details')!;
  view(definition, definition.path);
  expect(await screen.findByText('Redirect target')).toBeInTheDocument();
  expect(screen.getByTestId('location')).toHaveTextContent('/admin/sections');
});

describe('failed reads offer recovery', () => {
  it.each([
    '/admin/reports',
    '/admin/buildings',
    '/admin/requests',
    '/admin/audit-logs',
    '/admin/schedule-manager/drafts',
    '/admin/conflicts',
    '/admin/ai-scheduling',
    '/admin/institutional-rules',
    '/teacher/change-requests',
    '/teacher/report-issue',
  ])('%s says what could not load and offers Retry', async (path) => {
    reads.fail = true;
    const definition = routeDefinitions.find((item) => item.path === path)!;
    expect(definition, path).toBeDefined();
    view(definition, path);
    expect(
      (await screen.findAllByText(/^Couldn't load /, undefined, { timeout: 15000 })).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /^Retry/ }).length).toBeGreaterThan(0);
    reads.fail = false;
  }, 20000);
});
