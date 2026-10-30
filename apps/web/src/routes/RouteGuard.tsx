import { Link, Navigate, Outlet, useLocation } from 'react-router-dom';
import { DevelopmentRoleProvider } from '../auth/DevelopmentRoleProvider';
import { useDevelopmentRole } from '../auth/useDevelopmentRole';
import { AppShell } from '../components/layout/AppShell';
import { OperationsPreviewPage } from '../pages/OperationsPreviewPage';
import { ComingSoonPage } from '../pages/ComingSoonPage';
import { ProductScreenPage } from '../pages/ProductScreenPage';
import { dashboardPath } from './route-config';
import type { RouteDefinition } from './route-config';
import { capabilities } from '../config/runtime-config';
import { UniversitySessionProvider } from '../auth/UniversitySessionProvider';
import { useUniversitySession } from '../auth/university-session-context';
import { UniversitySessionPanel } from '../auth/UniversitySessionPanel';
import { StudentHome } from '../pages/StudentHome';
import { StructuredCalendarPage } from '../pages/StructuredCalendarPage';

function ConnectedStudentRoute({ definition }: { definition: RouteDefinition }) {
  const { state } = useUniversitySession();
  const location = useLocation();
  if (state.status === 'signed-out')
    return (
      <Navigate
        to={`/auth/login?returnTo=${encodeURIComponent(location.pathname + location.search)}`}
        replace
      />
    );
  if (state.status !== 'authorized')
    return (
      <main className="system-state-page">
        <section className="system-state">
          <h1>University access unavailable</h1>
          <UniversitySessionPanel />
          <Link className="button button--secondary" to="/auth/login">
            Return to access
          </Link>
        </section>
      </main>
    );
  if (state.membership.role !== 'student' || definition.role !== 'student')
    return (
      <main className="system-state-page">
        <section className="system-state">
          <h1>University access unavailable</h1>
          <p>This page requires a verified Student role.</p>
          <Link to="/auth/login">Check access</Link>
        </section>
      </main>
    );
  return (
    <AppShell>
      {definition.kind === 'dashboard' ? (
        <StudentHome />
      ) : ['schedule', 'calendar'].includes(definition.kind) ? (
        <StructuredCalendarPage role="student" />
      ) : definition.kind === 'notifications' ? (
        <StudentHome alerts />
      ) : ['rooms', 'room-detail'].includes(definition.kind) ? (
        <StudentHome key={definition.id} rooms roomDetail={definition.kind === 'room-detail'} />
      ) : (
        <section className="workspace-card">
          <h1>This service is not connected</h1>
          <Link to="/student/dashboard">Return home</Link>
        </section>
      )}
    </AppShell>
  );
}

export function RoleRoute({ definition }: { definition: RouteDefinition }) {
  const { role } = useDevelopmentRole();
  const location = useLocation();
  if (!capabilities.previewRoles) return <ConnectedStudentRoute definition={definition} />;
  if (!role)
    return (
      <Navigate
        to={`/auth/login?returnTo=${encodeURIComponent(location.pathname + location.search + location.hash)}`}
        replace
      />
    );
  if (role !== definition.role)
    return (
      <Navigate
        to={`/forbidden?returnTo=${encodeURIComponent(location.pathname + location.search + location.hash)}`}
        replace
      />
    );
  if (definition.kind === 'dashboard') return <OperationsPreviewPage />;
  if (definition.kind === 'coming-soon' && definition.plannedFeature)
    return (
      <AppShell>
        <ComingSoonPage feature={definition.plannedFeature} role={role} />
      </AppShell>
    );
  return <ProductScreenPage definition={definition} />;
}
export function ForbiddenPage() {
  const { role } = useDevelopmentRole();
  if (!role) return <Navigate to="/auth/login" replace />;
  return (
    <div className="system-state-page">
      <section className="system-state">
        <p className="eyebrow">Access restricted</p>
        <h1>This page is not available for your demo role.</h1>
        <p>Your current development preview is set to {role}.</p>
        <Link className="button" to={dashboardPath(role)}>
          Return to your dashboard
        </Link>
      </section>
    </div>
  );
}
export function RoleProviderLayout() {
  return (
    <DevelopmentRoleProvider>
      <UniversitySessionProvider>
        <Outlet />
      </UniversitySessionProvider>
    </DevelopmentRoleProvider>
  );
}
