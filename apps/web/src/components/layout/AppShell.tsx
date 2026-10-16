import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
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
import { previewContext, previewProfiles } from '../../data/schedule-preview';

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { role, signOut } = useDevelopmentRole();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [query, setQuery] = useState('');
  const main = useRef<HTMLElement>(null);
  const closeMenu = useCallback(() => setMobileOpen(false), []);

  useEffect(() => {
    closeMenu();
    setQuery('');
    // Also runs when switching screen families remounts the shell.
    main.current?.focus();
  }, [location.pathname, closeMenu]);

  useEffect(() => {
    const desktop = window.matchMedia('(min-width: 1024px)');
    const onResize = () => {
      if (desktop.matches) closeMenu();
    };
    desktop.addEventListener('change', onResize);
    return () => desktop.removeEventListener('change', onResize);
  }, [closeMenu]);

  if (!role) return <Navigate to="/dev/role-preview" replace />;
  const profile = previewProfiles[role];
  const groups = navigationForRole(role);
  const bottomItems = mobileNavigationForRole(role);
  const primaryItems = [...bottomItems];
  if (role !== 'student') {
    const requests = routeDefinitions.find((route) => route.path === rolePath(role, 'requests'));
    if (requests) primaryItems.splice(3, 0, requests);
  }
  const secondaryGroups = groups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (route) =>
          !primaryItems.some((primary) => primary.id === route.id) && route.kind !== 'settings',
      ),
    }))
    .filter((group) => group.items.length);
  const roleRoutes = routeDefinitions.filter((route) => route.role === role);
  const results = query.trim()
    ? roleRoutes
        .filter((route) =>
          (route.title + ' ' + route.description)
            .toLocaleLowerCase()
            .includes(query.trim().toLocaleLowerCase()),
        )
        .slice(0, 5)
    : [];
  const owner = navigationOwner(location.pathname);
  const mobileOwner = navigationOwner(location.pathname, true);
  const leaveDemo = () => {
    signOut();
    navigate('/auth/login', { replace: true });
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
        {group.title}
        <ChevronDown size={16} aria-hidden="true" />
      </summary>
      <div>{group.items.map(destination)}</div>
    </details>
  ));
  const accountLinks = (
    <div className="account-links">
      <Link className="nav-item" to={rolePath(role, 'profile')} onClick={closeMenu}>
        <UserRound size={18} aria-hidden="true" />
        Profile
      </Link>
      <Link className="nav-item" to={rolePath(role, 'settings')} onClick={closeMenu}>
        <Settings size={18} aria-hidden="true" />
        Settings
      </Link>
      <button className="nav-item" onClick={leaveDemo}>
        <LogOut size={18} aria-hidden="true" />
        Exit demo
      </button>
    </div>
  );

  return (
    <div className="app-shell brand-shell">
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
              <small>{profile.label} · Demo</small>
            </span>
          </Link>
          <div className="account-actions">
            <Link className="icon-button" to={rolePath(role, 'settings')} aria-label="Settings">
              <Settings size={18} />
            </Link>
            <button className="icon-button" onClick={leaveDemo} aria-label="Exit demo">
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
          <div className="semester">
            <span>{profile.label} demo</span>
            <strong>{previewContext.period}</strong>
          </div>
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
                placeholder="Search your workspace"
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
          <Link
            className="icon-button header-alerts"
            aria-label="Notifications"
            to={rolePath(role, 'notifications')}
          >
            <Bell />
          </Link>
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
