import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { DevelopmentRoleContext, type DevelopmentRoleContextValue } from '../auth/development-role-context';
import { RoleRoute } from './RouteGuard';
import { routeDefinitions } from './route-config';

function renderProtectedPath(role: DevelopmentRoleContextValue['role'], path: string) {
  const value: DevelopmentRoleContextValue = { role, startDemo: () => undefined, signOut: () => undefined };
  const definition = routeDefinitions.find(route => route.path === path);
  if (!definition) throw new Error(`Missing route definition for ${path}`);
  return render(<MemoryRouter initialEntries={[path]}><DevelopmentRoleContext.Provider value={value}><Routes><Route path="auth/login" element={<p>Public sign in</p>}/><Route path="forbidden" element={<p>Forbidden</p>}/><Route path={path.slice(1)} element={<RoleRoute definition={definition}/>}/></Routes></DevelopmentRoleContext.Provider></MemoryRouter>);
}

describe('protected role routes', () => {
  it('redirects an unsigned visitor to public sign in', () => {
    renderProtectedPath(null, '/student/schedule');
    expect(screen.getByText('Public sign in')).toBeInTheDocument();
  });

  it('redirects a demo role away from a route it does not own', () => {
    renderProtectedPath('student', '/admin/schedule-manager');
    expect(screen.getByText('Forbidden')).toBeInTheDocument();
  });
});
