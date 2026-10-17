import { Link, Navigate, Outlet, useLocation } from 'react-router-dom';
import { DevelopmentRoleProvider } from '../auth/DevelopmentRoleProvider';
import { useDevelopmentRole } from '../auth/useDevelopmentRole';
import { AppShell } from '../components/layout/AppShell';
import { OperationsPreviewPage } from '../pages/OperationsPreviewPage';
import { ComingSoonPage } from '../pages/ComingSoonPage';
import { ProductScreenPage } from '../pages/ProductScreenPage';
import { dashboardPath } from './route-config';
import type { RouteDefinition } from './route-config';

export function RoleRoute({ definition }: { definition: RouteDefinition }) {
  const { role } = useDevelopmentRole(); const location = useLocation();
  if (!role) return <Navigate to={`/auth/login?returnTo=${encodeURIComponent(location.pathname + location.search + location.hash)}`} replace/>;
  if (role !== definition.role) return <Navigate to={`/forbidden?returnTo=${encodeURIComponent(location.pathname + location.search + location.hash)}`} replace/>;
  if (definition.kind === 'dashboard') return <OperationsPreviewPage/>;
  if (definition.kind === 'coming-soon' && definition.plannedFeature) return <AppShell><ComingSoonPage feature={definition.plannedFeature} role={role}/></AppShell>;
  return <ProductScreenPage definition={definition}/>;
}
export function ForbiddenPage() { const { role } = useDevelopmentRole(); if (!role) return <Navigate to="/auth/login" replace/>; return <div className="system-state-page"><section className="system-state"><p className="eyebrow">Access restricted</p><h1>This page is not available for your demo role.</h1><p>Your current development preview is set to {role}.</p><Link className="button" to={dashboardPath(role)}>Return to your dashboard</Link></section></div>; }
export function RoleProviderLayout() { return <DevelopmentRoleProvider><Outlet/></DevelopmentRoleProvider>; }
