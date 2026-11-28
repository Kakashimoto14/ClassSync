import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { Bell, ChevronDown, LogOut, Menu, Search, Settings, UserRound } from 'lucide-react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useDevelopmentRole } from '../../auth/useDevelopmentRole';
import {
  dashboardPath,
  mobileNavigationForRole,
  navigationForRole,
  navigationOwner,
  rolePath,
  routeDefinitions,
  type RouteDefinition,
} from '../../routes/route-config';
import { Drawer } from '../ui/Drawer';
import { ClassSyncLogo } from '../brand/ClassSyncLogo';
import { capabilities } from '../../config/runtime-config';
import { previewProfiles } from '../../data/schedule-preview';
import { useUniversitySession } from '../../auth/university-session-context';

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const preview = useDevelopmentRole();
  const university = useUniversitySession();
  const institutional = !capabilities.previewRoles;
  const role = institutional
    ? university.state.status === 'authorized'
      ? university.state.membership.role
      : null
    : preview.role;
  const signOut = institutional ? university.signOut : preview.signOut;
  const [mobileOpen, setMobileOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [commandOpen, setCommandOpen] = useState(false);
  const main = useRef<HTMLElement>(null);
  const commandTrigger = useRef<HTMLButtonElement>(null);
  const commandMenu = useRef<HTMLElement>(null);
  const commandItems = useRef<Array<HTMLAnchorElement | null>>([]);
  const closeMenu = useCallback(() => setMobileOpen(false), []);

  useEffect(() => {
    closeMenu();
    setQuery('');
    setCommandOpen(false);
    // Also runs when switching screen families remounts the shell.
    main.current?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [location.pathname, closeMenu]);

  useEffect(() => {
    closeMenu();
    setQuery('');
    // Query-only changes (for example directory pagination) own their focus.
  }, [location.search, location.hash, closeMenu]);

  useEffect(() => {
    const desktop = window.matchMedia('(min-width: 1024px)');
    const onResize = () => {
      if (desktop.matches) closeMenu();
    };
    desktop.addEventListener('change', onResize);
    return () => desktop.removeEventListener('change', onResize);
  }, [closeMenu]);

  useEffect(() => {
    if (commandOpen) commandItems.current[0]?.focus();
    else commandItems.current = [];
  }, [commandOpen]);

  useEffect(() => {
    if (!commandOpen) return;
    const closeOutside = (event: PointerEvent) => {
      const target = event.target;
      if (
        target instanceof Node &&
        !commandMenu.current?.contains(target) &&
        !commandTrigger.current?.contains(target)
      )
        setCommandOpen(false);
    };
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, [commandOpen]);

  if (!role) return <Navigate to={institutional ? '/auth/login' : '/dev/role-preview'} replace />;
  const profile = institutional
    ? { name: 'University account', initials: 'CS', label: role === 'student' ? 'Student' : role }
    : previewProfiles[role];
  const availableRoute = (route: RouteDefinition) =>
    !route.plannedFeature &&
    (!institutional ||
      ([
        'dashboard',
        'schedule',
        'calendar',
        'rooms',
        'notifications',
        'announcements',
        'profile',
        'settings',
        'registration-scanner',
        'academic-manage',
        'requests',
        'request-detail',
        'request-create',
        'conflicts',
        'conflict-detail',
        'schedule-create',
        'schedule-drafts',
        'schedule-draft-detail',
        'audit',
        'academic-list',
        'scheduling-rules',
        'reports',
        'buildings',
        'report-issue',
      ].includes(route.kind) &&
        route.roomMode !== 'availability'));
  const groups = navigationForRole(role);
  const bottomItems = mobileNavigationForRole(role).filter(availableRoute);
  const primaryItems = [...bottomItems];
  if (role !== 'student') {
    const requests = routeDefinitions.find((route) => route.path === rolePath(role, 'requests'));
    if (
      requests &&
      availableRoute(requests) &&
      !primaryItems.some((item) => item.id === requests.id)
    )
      primaryItems.splice(3, 0, requests);
  }
  const secondaryGroups = groups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (route) =>
          !primaryItems.some((primary) => primary.id === route.id) &&
          route.kind !== 'settings' &&
          availableRoute(route),
      ),
    }))
    .filter((group) => group.items.length);
  const roleRoutes = routeDefinitions.filter(
    (route) =>
      route.role === role &&
      availableRoute(route) &&
      (route.navigationLabel || route.kind === 'profile' || route.kind === 'settings'),
  );
  const results = query.trim()
    ? roleRoutes
        .filter((route) =>
          (route.title + ' ' + route.description)
            .toLocaleLowerCase()
            .includes(query.trim().toLocaleLowerCase()),
        )
        .slice(0, 5)
    : [];
  const commandRoutes = roleRoutes.filter(
    (route) =>
      !route.path.includes(':') &&
      ![
        'academic-detail',
        'building-detail',
        'conflict-detail',
        'request-detail',
        'room-detail',
        'schedule-draft-detail',
      ].includes(route.kind),
  );
  const commandGroups = commandRoutes.reduce<Array<{ title: string; routes: RouteDefinition[] }>>(
    (groups, route) => {
      const title = route.navigationGroup ?? 'More destinations';
      const group = groups.find((item) => item.title === title);
      if (group) group.routes.push(route);
      else groups.push({ title, routes: [route] });
      return groups;
    },
    [],
  );

  const handleCommandKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Tab') {
      setCommandOpen(false);
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      setCommandOpen(false);
      commandTrigger.current?.focus();
      return;
    }
    const items = commandItems.current.filter(
      (item): item is HTMLAnchorElement => Boolean(item?.isConnected),
    );
    if (!items.length) return;
    const currentIndex = items.indexOf(document.activeElement as HTMLAnchorElement);
    let nextIndex: number | undefined;
    if (event.key === 'ArrowDown') nextIndex = (currentIndex + 1) % items.length;
    if (event.key === 'ArrowUp') nextIndex = (currentIndex - 1 + items.length) % items.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = items.length - 1;
    if (nextIndex !== undefined) {
      event.preventDefault();
      items[nextIndex]?.focus();
    }
  };
  const owner = navigationOwner(location.pathname);
  const mobileOwner = navigationOwner(location.pathname, true);
  const leaveDemo = () => {
    // Leave the guarded route before clearing its role, so its missing-session
    // redirect cannot race the explicit Exit destination.
    navigate('/auth/login', { replace: true, flushSync: true });
    signOut();
  };
  const destination = (route: RouteDefinition) => (
    <Link
      key={route.id}
      className={'nav-item' + (owner === route.id ? ' nav-item--active' : '')}
      aria-current={
        location.pathname === route.path ? 'page' : owner === route.id ? 'location' : undefined
      }
      to={route.path}
      onClick={closeMenu}
    >
      <route.icon size={18} aria-hidden="true" />
      <span>
        {route.navigationLabel ?? route.title}
        {route.plannedFeature && <small>Coming Soon</small>}
      </span>
    </Link>
  );
  const secondaryNavigation = secondaryGroups.map((group) => (
    <details
      className="nav-group"
      key={group.title + location.pathname}
      open={group.items.some((route) => route.id === owner)}
    >
      <summary>
        {role === 'student' && group.title === 'Rooms' ? 'Room tools' : group.title}
        <ChevronDown size={16} aria-hidden="true" />
      </summary>
      <div>{group.items.map(destination)}</div>
    </details>
  ));
  const accountLinks = (
    <div className="account-links">
      {institutional && (
        <Link className="nav-item" to="/auth/account" onClick={closeMenu}>
          {role === 'administrator' ? 'University accounts' : 'Account access'}
        </Link>
      )}
      {!institutional && (
        <>
          <Link className="nav-item" to={rolePath(role, 'profile')} onClick={closeMenu}>
            <UserRound size={18} aria-hidden="true" />
            Profile
          </Link>
          <Link className="nav-item" to={rolePath(role, 'settings')} onClick={closeMenu}>
            <Settings size={18} aria-hidden="true" />
            Settings
          </Link>
        </>
      )}
      <button className="nav-item" onClick={leaveDemo}>
        <LogOut size={18} aria-hidden="true" />
        {institutional ? 'Sign out' : 'Exit demo'}
      </button>
      {!institutional && (
        <Link className="nav-item" to="/dev/role-preview" onClick={closeMenu}>
          Switch preview role
        </Link>
      )}
    </div>
  );

  return (
    <div className={`app-shell brand-shell ${role === 'student' ? 'student-shell' : ''}`}>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar" aria-label="Workspace sidebar">
        <Link className="brand" to={dashboardPath(role)} aria-label="ClassSync home">
          <ClassSyncLogo decorative />
        </Link>
        <nav className="sidebar-navigation" aria-label="Primary navigation">
          <div className="primary-links">{primaryItems.map(destination)}</div>
          {secondaryNavigation}
        </nav>
        <div className="sidebar-user">
          <Link className="sidebar-profile" to={rolePath(role, 'profile')}>
            <span className="avatar">{profile.initials}</span>
            <span>
              <strong>{profile.name}</strong>
              <small>
                {profile.label}
                {` · ${institutional ? 'University' : 'Demo'}`}
              </small>
            </span>
          </Link>
          <div className="account-actions">
            {!institutional && (
              <Link className="icon-button" to={rolePath(role, 'settings')} aria-label="Settings">
                <Settings size={18} />
              </Link>
            )}
            <button
              className="icon-button"
              onClick={leaveDemo}
              aria-label={institutional ? 'Sign out' : 'Exit demo'}
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-start">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation menu"
              aria-expanded={mobileOpen}
              aria-haspopup="dialog"
              onClick={() => setMobileOpen(true)}
            >
              <Menu />
            </button>
            <Link className="mobile-brand" to={dashboardPath(role)} aria-label="ClassSync home">
              <ClassSyncLogo size="small" decorative />
            </Link>
          </div>
          {role === 'student' && (
            <div className="student-header-location">
              <span>Student</span>
              <span aria-hidden="true">/</span>
              <strong>
                {routeDefinitions.find((route) => route.id === owner)?.navigationLabel ??
                  'Workspace'}
              </strong>
            </div>
          )}
          <div className="semester">
            <details
              className="preview-indicator"
              key={location.pathname}
              onKeyDown={(event) => {
                if (event.key === 'Escape') {
                  event.currentTarget.open = false;
                  event.currentTarget.querySelector('summary')?.focus();
                }
              }}
            >
              <summary>
                {profile.label} {institutional ? 'workspace' : 'demo'}{' '}
                <ChevronDown size={14} aria-hidden="true" />
              </summary>
              <div className="preview-menu">
                <p>
                  {institutional
                    ? 'Access is checked against your current university membership. Published schedules only.'
                    : `Preview role only; no account is authenticated. ${capabilities.description}`}
                </p>
                <Link
                  className="text-action"
                  to={institutional ? '/auth/account' : '/dev/role-preview'}
                >
                  {institutional
                    ? role === 'administrator'
                      ? 'University accounts'
                      : 'Account access'
                    : 'Switch preview role'}
                </Link>
              </div>
            </details>
            {role !== 'student' && (
              <strong>
                Asia/Manila · {institutional ? 'University workspace' : 'Preview workspace'}
              </strong>
            )}
          </div>
          {role === 'administrator' ? (
            <div className="global-search command-navigation">
              <button
                ref={commandTrigger}
                className="header-search command-trigger"
                type="button"
                aria-label="Open page menu"
                aria-haspopup="menu"
                aria-expanded={commandOpen}
                aria-controls="admin-command-menu"
                onClick={() => setCommandOpen((open) => !open)}
              >
                <Search size={18} aria-hidden="true" />
                <span>Choose a page</span>
              </button>
              {commandOpen && (
                <nav
                  id="admin-command-menu"
                  ref={commandMenu}
                  className="command-menu"
                  role="menu"
                  aria-label="Administrator destinations"
                  aria-orientation="vertical"
                  onKeyDown={handleCommandKeyDown}
                >
                  {commandGroups.map((group) => (
                    <div role="group" aria-label={group.title} key={group.title}>
                      <p>{group.title}</p>
                      {group.routes.map((route) => (
                        <Link
                          role="menuitem"
                          tabIndex={-1}
                          key={route.id}
                          to={route.path}
                          ref={(element) => {
                            const index = commandRoutes.findIndex((item) => item.id === route.id);
                            commandItems.current[index] = element;
                          }}
                          onClick={() => setCommandOpen(false)}
                          aria-current={location.pathname === route.path ? 'page' : undefined}
                        >
                          <route.icon size={16} aria-hidden="true" />
                          <span>{route.title}</span>
                        </Link>
                      ))}
                    </div>
                  ))}
                </nav>
              )}
            </div>
          ) : (
            <div
              className="global-search"
              onKeyDown={(event) => {
                if (event.key === 'Escape') setQuery('');
              }}
            >
              <label className="header-search">
                <Search size={18} aria-hidden="true" />
                <input
                  aria-label="Search ClassSync"
                  placeholder="Find a page"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              {query.trim() && (
                <div className="search-results">
                  <nav aria-label="Search destinations">
                    {results.map((route) => (
                      <Link to={route.path} key={route.id} onClick={() => setQuery('')}>
                        <route.icon size={16} aria-hidden="true" />
                        <span>{route.title}</span>
                      </Link>
                    ))}
                  </nav>
                  {!results.length && <p role="status">No matching pages in your workspace.</p>}
                </div>
              )}
            </div>
          )}
          {!institutional && (
            <Link
              className="icon-button header-alerts"
              aria-label="Notifications"
              to={rolePath(role, 'notifications')}
            >
              <Bell />
            </Link>
          )}
        </header>
        <main id="main-content" className="main-content" ref={main} tabIndex={-1}>
          {children}
        </main>
      </div>
      <nav className="bottom-nav" aria-label="Mobile navigation">
        {bottomItems.map((route) => (
          <Link
            key={route.id}
            to={route.path}
            className={mobileOwner === route.id ? 'bottom-nav--active' : ''}
            aria-current={
              mobileOwner === route.id
                ? location.pathname === route.path
                  ? 'page'
                  : 'location'
                : undefined
            }
          >
            <route.icon size={20} aria-hidden="true" />
            <span>{route.mobileLabel ?? route.navigationLabel}</span>
          </Link>
        ))}
      </nav>
      {mobileOpen && (
        <Drawer title={profile.label + ' menu'} onClose={closeMenu}>
          <nav className="mobile-drawer-nav" aria-label={profile.label + ' secondary navigation'}>
            {primaryItems
              .filter((route) => !bottomItems.some((item) => item.id === route.id))
              .map(destination)}
            {secondaryNavigation}
            {accountLinks}
          </nav>
        </Drawer>
      )}
    </div>
  );
}
