import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DevelopmentRoleContext } from '../../auth/development-role-context';
import {
  mobileNavigationForRole,
  navigationForRole,
  navigationOwner,
  routeDefinitions,
} from '../../routes/route-config';
import type { UserRole } from '../../types/ui';
import { AppShell } from './AppShell';

beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
});

function renderShell(role: UserRole, path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <DevelopmentRoleContext.Provider value={{ role, startDemo: vi.fn(), signOut: vi.fn() }}>
        <Routes>
          <Route
            path="*"
            element={
              <AppShell>
                <h1>Workspace content</h1>
              </AppShell>
            }
          />
        </Routes>
      </DevelopmentRoleContext.Provider>
    </MemoryRouter>,
  );
}

describe('workspace navigation', () => {
  it.each(['student', 'teacher', 'administrator'] as const)(
    'keeps every %s navigation and account link registered and role-owned',
    (role) => {
      const path = role === 'administrator' ? '/admin/dashboard' : '/' + role + '/dashboard';
      renderShell(role, path);
      const registered = routeDefinitions
        .filter((route) => route.role === role)
        .map((route) => route.path);
      for (const link of screen.getAllByRole('link', { hidden: true })) {
        const href = link.getAttribute('href');
        if (href !== '#main-content') expect(registered).toContain(href);
      }
      const navigation = screen.getByRole('navigation', { name: 'Primary navigation' });
      const links = [...navigation.querySelectorAll('a')].map((link) => link.getAttribute('href'));
      expect(new Set(links).size).toBe(links.length);
      for (const route of navigationForRole(role).flatMap((group) => group.items)) {
        if (route.kind !== 'settings') expect(links).toContain(route.path);
      }
    },
  );

  it('preserves the four Student mobile destinations and closes the secondary drawer after navigation', () => {
    renderShell('student', '/student/dashboard');
    const bottom = screen.getByRole('navigation', { name: 'Mobile navigation' });
    expect(
      within(bottom)
        .getAllByRole('link')
        .map((link) => link.textContent),
    ).toEqual(['Home', 'Schedule', 'Rooms', 'Alerts']);
    const trigger = screen.getByRole('button', { name: 'Open navigation menu' });
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    const dialog = screen.getByRole('dialog', { name: 'Student menu' });
    fireEvent.click(within(dialog).getByRole('link', { name: 'Settings' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByRole('main')).toHaveFocus();
  });

  it('keeps Schedule active on administrator creation and Calendar active in Student secondary navigation', () => {
    expect(navigationOwner('/admin/schedule-manager/create')).toBe(
      'administrator.schedule-manager',
    );
    expect(navigationOwner('/admin/schedule-manager/create', true)).toBe(
      'administrator.schedule-manager',
    );
    expect(navigationOwner('/student/calendar')).toBe('student.calendar');
    expect(navigationOwner('/student/calendar', true)).toBe('student.schedule');
    renderShell('administrator', '/admin/schedule-manager/create');
    expect(
      within(screen.getByRole('navigation', { name: 'Primary navigation' })).getByRole('link', {
        name: 'Schedule Manager',
      }),
    ).toHaveAttribute('aria-current', 'location');
  });

  it('uses ordinary accessible links for destination search', () => {
    renderShell('administrator', '/admin/dashboard');
    fireEvent.change(screen.getByRole('textbox', { name: 'Search ClassSync' }), {
      target: { value: 'Profile' },
    });
    expect(
      within(screen.getByRole('navigation', { name: 'Search destinations' })).getByRole('link', {
        name: 'Profile',
      }),
    ).toHaveAttribute('href', '/admin/profile');
    fireEvent.keyDown(screen.getByRole('textbox', { name: 'Search ClassSync' }), { key: 'Escape' });
    expect(
      screen.queryByRole('navigation', { name: 'Search destinations' }),
    ).not.toBeInTheDocument();
  });

  it('resolves every navigation owner within the route role', () => {
    for (const route of routeDefinitions) {
      const owner = navigationOwner(route.path);
      if (owner) expect(routeDefinitions.find((item) => item.id === owner)?.role).toBe(route.role);
      const mobile = navigationOwner(route.path, true);
      if (mobile)
        expect(mobileNavigationForRole(route.role).some((item) => item.id === mobile)).toBe(true);
    }
  });
});
