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
  it('discloses preview options and closes them with Escape without changing role', () => {
    renderShell('student', '/student/dashboard');
    const summary = screen.getByText('Student demo');
    const details = summary.closest('details')!;
    fireEvent.click(summary);
    expect(details).toHaveAttribute('open');
    expect(within(details).getByRole('link', { name: 'Switch preview role' })).toHaveAttribute(
      'href',
      '/dev/role-preview',
    );
    fireEvent.keyDown(summary, { key: 'Escape' });
    expect(details).not.toHaveAttribute('open');
    expect(summary).toHaveFocus();
  });
  it('takes Teacher Rooms directly to the working resource directory', () => {
    const rooms = mobileNavigationForRole('teacher').find((route) => route.mobileLabel === 'Rooms');
    expect(rooms?.path).toBe('/teacher/find-room');
    expect(navigationOwner('/teacher/room-availability', true)).toBe('teacher.find-room');
    expect(navigationOwner('/teacher/rooms/detail', true)).toBe('teacher.find-room');
  });
  it('offers a selection-only Administrator page menu without record details', () => {
    renderShell('administrator', '/admin/dashboard');
    expect(screen.queryByRole('textbox', { name: 'Search ClassSync' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Open page menu' }));
    const menu = within(screen.getByRole('menu', { name: 'Administrator destinations' }));
    expect(menu.getByRole('menuitem', { name: 'Room Directory' })).toHaveAttribute(
      'href',
      '/admin/rooms',
    );
    expect(menu.queryByRole('menuitem', { name: 'Room Details' })).not.toBeInTheDocument();
    expect(menu.queryByRole('menuitem', { name: 'Conflict Details' })).not.toBeInTheDocument();
  });

  it('supports arrow navigation and Escape focus restoration in the Administrator menu', () => {
    renderShell('administrator', '/admin/dashboard');
    const trigger = screen.getByRole('button', { name: 'Open page menu' });
    fireEvent.click(trigger);
    const menu = screen.getByRole('menu', { name: 'Administrator destinations' });
    const first = within(menu).getAllByRole('menuitem')[0];
    const second = within(menu).getAllByRole('menuitem')[1];
    expect(first).toHaveFocus();
    fireEvent.keyDown(menu, { key: 'ArrowDown' });
    expect(second).toHaveFocus();
    fireEvent.keyDown(menu, { key: 'End' });
    expect(within(menu).getAllByRole('menuitem').at(-1)).toHaveFocus();
    fireEvent.keyDown(menu, { key: 'Escape' });
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    fireEvent.click(trigger);
    fireEvent.keyDown(screen.getByRole('menu'), { key: 'Tab' });
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });
  it('focuses the destination and returns to its heading after navigation', () => {
    renderShell('student', '/student/dashboard');
    vi.mocked(window.scrollTo).mockClear();
    fireEvent.click(
      within(screen.getByRole('navigation', { name: 'Mobile navigation' })).getByRole('link', {
        name: 'Rooms',
      }),
    );
    expect(screen.getByRole('main')).toHaveFocus();
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' });
  });
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
        if (href === '/dev/role-preview') expect(link).toHaveTextContent('Switch preview role');
        else if (href !== '#main-content') expect(registered).toContain(href);
      }
      const navigation = screen.getByRole('navigation', { name: 'Primary navigation' });
      const links = [...navigation.querySelectorAll('a')].map((link) => link.getAttribute('href'));
      expect(new Set(links).size).toBe(links.length);
      for (const route of navigationForRole(role).flatMap((group) => group.items)) {
        if (route.plannedFeature) expect(links).not.toContain(route.path);
        else if (route.kind !== 'settings') expect(links).toContain(route.path);
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

  it('keeps generation active and consolidates the calendar alias under Schedule', () => {
    expect(navigationOwner('/admin/schedule-manager/create')).toBe('administrator.ai-scheduling');
    expect(navigationOwner('/admin/schedule-manager/create', true)).toBe(
      'administrator.ai-scheduling',
    );
    expect(navigationOwner('/student/calendar')).toBe('student.schedule');
    expect(navigationOwner('/student/calendar', true)).toBe('student.schedule');
    renderShell('administrator', '/admin/schedule-manager/create');
    expect(
      within(screen.getByRole('navigation', { name: 'Primary navigation' })).getByRole('link', {
        name: 'Schedule Generation',
      }),
    ).toHaveAttribute('aria-current', 'location');
  });

  it('condenses academic data entry in the sidebar while keeping category destinations searchable', () => {
    renderShell('administrator', '/admin/dashboard');
    const navigation = screen.getByRole('navigation', { name: 'Primary navigation' });
    expect(within(navigation).getByRole('link', { name: 'Academic Setup' })).toHaveAttribute(
      'href',
      '/admin/academic',
    );
    for (const label of ['Faculty', 'Subjects', 'Sections', 'Programs', 'Subject Offerings']) {
      expect(within(navigation).queryByRole('link', { name: label })).not.toBeInTheDocument();
    }
    fireEvent.click(screen.getByRole('button', { name: 'Open page menu' }));
    expect(
      within(screen.getByRole('menu', { name: 'Administrator destinations' })).getByRole('menuitem', {
        name: 'Faculty',
      }),
    ).toHaveAttribute('href', '/admin/teachers');
  });

  it('preserves ordinary accessible destination search for non-Administrator roles', () => {
    renderShell('student', '/student/dashboard');
    fireEvent.change(screen.getByRole('textbox', { name: 'Search ClassSync' }), {
      target: { value: 'Profile' },
    });
    expect(
      within(screen.getByRole('navigation', { name: 'Search destinations' })).getByRole('link', {
        name: 'Profile',
      }),
    ).toHaveAttribute('href', '/student/profile');
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
