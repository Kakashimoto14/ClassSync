import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppShell } from './AppShell';
import { navigationOwner, navigationTrail, routeDefinitions } from '../../routes/route-config';

const session = vi.hoisted(() => ({ role: 'administrator' }));
vi.mock('../../config/runtime-config', () => ({
  capabilities: { previewRoles: false, description: '' },
}));
vi.mock('../../auth/useDevelopmentRole', () => ({
  useDevelopmentRole: () => ({ role: null, signOut: vi.fn() }),
}));
vi.mock('../../auth/university-session-context', () => ({
  useUniversitySession: () => ({
    state: { status: 'authorized', membership: { role: session.role } },
    signOut: vi.fn(),
  }),
}));

beforeEach(() => {
  session.role = 'administrator';
  window.scrollTo = vi.fn();
  window.matchMedia = vi.fn().mockReturnValue({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  });
});

const shell = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppShell>
        <h1>Content</h1>
      </AppShell>
    </MemoryRouter>,
  );

describe('Phase D shell', () => {
  it.each(['administrator', 'teacher', 'student'] as const)(
    'gives every nested %s page a sidebar owner',
    (role) => {
      const orphans = routeDefinitions.filter(
        (route) =>
          route.role === role &&
          // Account pages sit under the account links, not a navigation group.
          !['profile', 'settings'].includes(route.kind) &&
          !navigationOwner(route.path),
      );
      expect(orphans.map((route) => route.path)).toEqual([]);
    },
  );

  it.each([
    ['/admin/students', 'Academic Setup'],
    ['/admin/teachers', 'Academic Setup'],
    ['/admin/subjects', 'Academic Setup'],
    ['/admin/sections', 'Academic Setup'],
    ['/admin/buildings', 'Campus'],
    ['/admin/reports', 'Insights'],
    ['/admin/institutional-rules', 'System'],
    ['/admin/schedule-manager/drafts', 'Scheduling'],
    ['/admin/schedule-manager/drafts/abc', 'Scheduling'],
  ])('opens and marks the parent group on %s', (path, title) => {
    shell(path);
    const sidebar = screen.getByRole('navigation', { name: 'Primary navigation' });
    const group = within(sidebar).getByText(title, { selector: 'summary' }).closest('details');
    expect(group).toHaveAttribute('open');
    expect(group).toHaveClass('nav-group--active');
    expect(group?.querySelector('[aria-current]')).not.toBeNull();
  });

  it('shows breadcrumbs on subpages only, with the parent as a link', () => {
    const view = shell('/admin/schedule-manager/drafts/abc');
    const crumbs = screen.getByRole('navigation', { name: 'Breadcrumb' });
    expect(within(crumbs).getByRole('link', { name: 'Saved Drafts' })).toHaveAttribute(
      'href',
      '/admin/schedule-manager/drafts',
    );
    expect(crumbs.querySelector('[aria-current="page"]')).not.toBeNull();
    view.unmount();
    shell('/admin/dashboard');
    expect(screen.queryByRole('navigation', { name: 'Breadcrumb' })).not.toBeInTheDocument();
    expect(navigationTrail('/admin/students')).toEqual([
      { label: 'Academic Setup' },
      { label: 'Students' },
    ]);
  });

  it.each([
    ['administrator', '/admin/dashboard', 'Administrator Workspace'],
    ['teacher', '/teacher/dashboard', 'Teacher Workspace'],
    ['student', '/student/dashboard', 'Student Workspace'],
  ])('titles the %s workspace in Title Case', (role, path, title) => {
    session.role = role;
    shell(path);
    expect(screen.getByText(title, { selector: 'summary' })).toBeInTheDocument();
  });

  it('shows the campus time zone chip', () => {
    shell('/admin/dashboard');
    expect(screen.getByText('Asia/Manila · PHT')).toBeInTheDocument();
  });

  it('keeps the skip link clipped until keyboard focus', () => {
    const css = readFileSync(resolve(__dirname, '../../styles.css'), 'utf8').replace(/\r/g, '');
    const hidden = /\.skip-link \{([^}]*)\}/.exec(css)![1];
    expect(hidden).toContain('clip-path: inset(50%)');
    expect(hidden).toContain('width: 1px');
    expect(/\.skip-link:focus-visible \{([^}]*)\}/.exec(css)![1]).toContain('clip-path: none');
    expect(css).not.toMatch(/\.skip-link:focus \{/);
    shell('/admin/dashboard');
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute(
      'href',
      '#main-content',
    );
  });
});
