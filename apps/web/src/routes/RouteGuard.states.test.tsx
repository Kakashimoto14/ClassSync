import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { RoleRoute } from './RouteGuard';
import { routeDefinitions } from './route-config';
import { UniversitySessionContext } from '../auth/university-session-context';
import type { UniversitySession } from '../auth/university-session';

vi.mock('../config/runtime-config', async (original) => ({
  ...(await original<typeof import('../config/runtime-config')>()),
  capabilities: { previewRoles: false, description: '' },
}));

vi.mock('../auth/useDevelopmentRole', () => ({
  useDevelopmentRole: () => ({ role: null, signOut: vi.fn() }),
}));

const refresh = vi.fn();
const signOut = vi.fn();
const definition = routeDefinitions.find((route) => route.path === '/admin/dashboard')!;
const guard = (state: UniversitySession) =>
  render(
    <MemoryRouter initialEntries={[definition.path]}>
      <UniversitySessionContext.Provider value={{ available: true, state, refresh, signOut }}>
        <RoleRoute definition={definition} />
      </UniversitySessionContext.Provider>
    </MemoryRouter>,
  );

beforeEach(() => vi.clearAllMocks());

it('offers a primary Retry before an outlined Sign out when access is unavailable', () => {
  guard({ status: 'unavailable' });
  expect(screen.getByRole('img', { name: 'ClassSync' })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'University access unavailable' })).toBeInTheDocument();
  const retry = screen.getByRole('button', { name: 'Retry access check' });
  const leave = screen.getByRole('button', { name: 'Sign out' });
  expect(retry).toHaveClass('button--primary');
  expect(leave).toHaveClass('button--secondary');
  expect(retry.compareDocumentPosition(leave) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  fireEvent.click(retry);
  expect(refresh).toHaveBeenCalledOnce();
  expect(screen.getByRole('link', { name: 'Return to access' })).toHaveAttribute('href', '/auth/login');
});

it('gives a role mismatch both a way back and a way out', () => {
  guard({
    status: 'authorized',
    membership: {
      uid: 'u', tenant_id: 't', role: 'student', membership_revision: 1,
      available_roles: ['student'],
    },
  } as UniversitySession);
  expect(screen.getByRole('link', { name: 'Check access' })).toHaveClass('button');
  fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
  expect(signOut).toHaveBeenCalledOnce();
});

it('shows a calm waking state with a decorative skeleton', () => {
  const { container } = guard({ status: 'checking', waking: true } as UniversitySession);
  expect(screen.getByRole('status')).toHaveTextContent('Waking university services…');
  expect(container.querySelector('.classsync-page-loader__bars')).toHaveAttribute('aria-hidden', 'true');
});
