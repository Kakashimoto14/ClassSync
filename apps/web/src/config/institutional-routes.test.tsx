import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { DevelopmentRoleContext } from '../auth/development-role-context';
import { RoleRoute } from '../routes/RouteGuard';
import { routeDefinitions } from '../routes/route-config';
import { UniversitySessionContext } from '../auth/university-session-context';
vi.mock('../pages/StudentHome', () => ({ StudentHome: () => <h1>Connected Student Home</h1> }));

vi.mock('./runtime-config', async () => {
  const { capabilitiesFor } = await import('./app-mode');
  return { appMode: 'institutional', capabilities: capabilitiesFor('institutional') };
});
it.each(['student', 'teacher', 'administrator'] as const)(
  'rejects stored/client-selected %s as an institutional identity',
  (role) => {
    const fetcher = vi.spyOn(globalThis, 'fetch');
    render(
      <MemoryRouter>
        <DevelopmentRoleContext.Provider value={{ role, startDemo: vi.fn(), signOut: vi.fn() }}>
          <RoleRoute
            definition={routeDefinitions.find((r) => r.role === role && r.kind === 'dashboard')!}
          />
        </DevelopmentRoleContext.Provider>
      </MemoryRouter>,
    );
    expect(
      screen.getByRole('heading', { name: 'University access unavailable' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Return to access' })).toHaveAttribute(
      'href',
      '/auth/login',
    );
    expect(fetcher).not.toHaveBeenCalled();
    fetcher.mockRestore();
  },
);
it('opens only the verified Student workspace and ignores a conflicting preview persona', () => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
  render(
    <MemoryRouter>
      <DevelopmentRoleContext.Provider
        value={{ role: 'administrator', startDemo: vi.fn(), signOut: vi.fn() }}
      >
        <UniversitySessionContext.Provider
          value={{
            available: true,
            state: {
              status: 'authorized',
              membership: {
                uid: 'synthetic',
                tenant_id: 'test',
                role: 'student',
                student_id: 'student-a',
                membership_revision: 1,
              },
            },
            refresh: vi.fn(),
            signOut: vi.fn(),
          }}
        >
          <RoleRoute
            definition={routeDefinitions.find(
              (r) => r.role === 'student' && r.kind === 'dashboard',
            )!}
          />
        </UniversitySessionContext.Provider>
      </DevelopmentRoleContext.Provider>
    </MemoryRouter>,
  );
  expect(screen.getByRole('heading', { name: 'Connected Student Home' })).toBeInTheDocument();
  expect(screen.getByText('Student · University')).toBeInTheDocument();
  expect(screen.queryByText('Maria Santos')).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Switch preview role' })).not.toBeInTheDocument();
});
