import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { UniversitySessionContext } from '../auth/university-session-context';
import { DevelopmentRoleContext } from '../auth/development-role-context';
import type { UniversitySession } from '../auth/university-session';
import { RoleRoute } from './RouteGuard';
import { routeDefinitions } from './route-config';
vi.mock('../config/runtime-config', async () => {
  const { capabilitiesFor } = await import('../config/app-mode');
  return { appMode: 'institutional', capabilities: capabilitiesFor('institutional') };
});
vi.mock('../components/layout/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}));
vi.mock('../pages/StructuredCalendarPage', () => ({
  StructuredCalendarPage: ({ role }: { role: string }) => <p>Connected {role} timetable</p>,
}));
vi.mock('../pages/AcademicManagementPage', () => ({
  AcademicManagementPage: () => <p>Connected academic inputs</p>,
}));
function view(state: UniversitySession, path = '/teacher/schedule') {
  return (
    <MemoryRouter>
      <DevelopmentRoleContext.Provider
        value={{ role: 'administrator', startDemo: vi.fn(), signOut: vi.fn() }}
      >
        <UniversitySessionContext.Provider
          value={{ available: true, state, refresh: vi.fn(), signOut: vi.fn() }}
        >
          <RoleRoute definition={routeDefinitions.find((item) => item.path === path)!} />
        </UniversitySessionContext.Provider>
      </DevelopmentRoleContext.Provider>
    </MemoryRouter>
  );
}
const teacher: UniversitySession = {
  status: 'authorized',
  membership: {
    uid: 'owned-user',
    tenant_id: 'owned-tenant',
    role: 'teacher',
    faculty_id: 'approved-faculty',
    membership_revision: 1,
  },
};
it('admits the verified Teacher and hides the timetable when current access is denied', () => {
  const result = render(view(teacher));
  expect(screen.getByText('Connected teacher timetable')).toBeInTheDocument();
  result.rerender(view({ status: 'denied' }));
  expect(screen.queryByText('Connected teacher timetable')).not.toBeInTheDocument();
});
it('rejects a Teacher at Administrator inputs even when the browser preview role is Administrator', () => {
  render(view(teacher, '/admin/academic'));
  expect(screen.queryByText('Connected academic inputs')).not.toBeInTheDocument();
  expect(
    screen.getByText('This page requires your university to grant the matching workspace role.'),
  ).toBeInTheDocument();
});
it('admits current Administrator inputs through the connected branch', () => {
  render(
    view(
      {
        status: 'authorized',
        membership: {
          uid: 'approved-admin',
          tenant_id: 'owned-tenant',
          role: 'administrator',
          membership_revision: 2,
        },
      },
      '/admin/academic',
    ),
  );
  expect(screen.getByText('Connected academic inputs')).toBeInTheDocument();
});
