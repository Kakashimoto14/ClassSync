import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppShell } from './AppShell';
import { ClassSyncPageSkeleton } from '../loading/ClassSyncLoading';
import { navigationOwner, routeDefinitions } from '../../routes/route-config';

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

const src = resolve(__dirname, '../..');
const sheet = (path: string) => readFileSync(resolve(src, path), 'utf8').replace(/\r/g, '');
const shell = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppShell>
        <h1>Content</h1>
      </AppShell>
    </MemoryRouter>,
  );

// Every nested page that has its own sidebar owner, with record ids filled in.
const nested = routeDefinitions
  .filter((route) => {
    const owner = navigationOwner(route.path);
    return owner && owner !== route.id;
  })
  .map((route) => [route.role, route.path.replace(/:[^/]+/g, 'abc')] as const);

describe('Phase E shell', () => {
  it.each(nested)('draws one active sidebar item and its group for %s %s', (role, path) => {
    session.role = role;
    shell(path);
    const sidebar = screen.getByRole('navigation', { name: 'Primary navigation' });
    const active = sidebar.querySelectorAll('.nav-item--active');
    expect(active).toHaveLength(1);
    expect(active[0]).toHaveAttribute('aria-current', 'location');
    const group = active[0].closest('details');
    if (group) {
      expect(group).toHaveClass('nav-group--active');
      expect(group).toHaveAttribute('open');
    }
  });

  it('styles the active item with a 3px crimson bar and a soft pill', () => {
    const css = sheet('components/layout/app-shell.css');
    expect(css).toMatch(/\.nav-item--active::before \{[^}]*width: 3px;[^}]*var\(--brand-crimson\)/);
    expect(css).toMatch(/\.nav-item--active,\n\.nav-item--active:hover \{\n {2}background: var\(--brand-crimson-soft\)/);
  });

  it('puts the breadcrumb, time zone, page switcher and account menu in the top bar', () => {
    shell('/admin/schedule-manager/drafts/abc');
    const bar = within(screen.getByRole('banner'));
    expect(bar.getByRole('navigation', { name: 'Breadcrumb' })).toBeInTheDocument();
    expect(bar.getByText('Asia/Manila · PHT')).toBeInTheDocument();
    expect(bar.getByRole('button', { name: 'Open page menu' })).toBeInTheDocument();
    expect(bar.getByText('Administrator Workspace', { selector: 'summary' })).toBeInTheDocument();
    expect(within(screen.getByRole('main')).queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('keeps tokens first and free of overrides in the migrated sheets', () => {
    expect(sheet('styles.css').startsWith("@import './tokens.css';")).toBe(true);
    for (const path of ['theme.css', 'pages/institutional-entrance.css']) {
      expect(sheet(path)).not.toContain('!important');
      expect(sheet(path)).not.toMatch(/#[0-9a-f]{3,8}\b/i);
    }
    const tokens = sheet('tokens.css');
    expect(tokens).toContain('--brand-crimson: #991b2e;');
    expect(tokens).toContain('--control-h: 36px;');
    expect(tokens).toMatch(/@media \(pointer: coarse\) \{\s*:root \{\s*--control-h: 44px;/);
  });

  it('leaves the previous rouge brand in no stylesheet', () => {
    const files = [...readdirSync(src), ...readdirSync(resolve(src, 'pages')).map((f) => 'pages/' + f)]
      .filter((file) => file.endsWith('.css'));
    for (const file of files) expect(sheet(file), file).not.toMatch(/#872e49|#8a2b45|135 46 73/i);
  });

  it.each([
    ['/admin/dashboard', 'kpis'],
    ['/teacher/schedule', 'timetable'],
    ['/admin/students', 'table'],
  ])('shapes the loading skeleton like %s', (path, layout) => {
    const { container } = render(<ClassSyncPageSkeleton path={path} label="Loading page" />);
    expect(screen.getByRole('status', { name: 'Loading page' })).toHaveClass(`classsync-skeleton--${layout}`);
    expect(container.querySelector('main')).toBeNull();
  });
});
