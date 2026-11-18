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
import { StudentRooms } from '../pages/StudentRooms';
import { StructuredCalendarPage } from '../pages/StructuredCalendarPage';
import { RegistrationScannerPage } from '../pages/RegistrationScannerPage';
import { AcademicManagementPage } from '../pages/AcademicManagementPage';
import { SchedulingSourcePage } from '../pages/AcademicGenerationPage';
import { SavedDraftsPage, SavedDraftDetailPage } from '../pages/SchedulingDraftPages';
import { PublicationAuditPage } from '../pages/PublicationAuditPage';
import { ConflictCenterPage } from '../pages/ConflictCenterPage';
import { ClassroomRequestsPage } from '../pages/ClassroomRequestsPage';
import { ConnectedRoomsPage } from '../pages/ConnectedRoomsPage';
import { AnnouncementsPage } from '../pages/AnnouncementsPage';
import { AccountProfilePage } from '../pages/AccountProfilePage';
import { ConnectedUpdatesPage } from '../pages/ConnectedUpdatesPage';

function ConnectedUniversityRoute({ definition }: { definition: RouteDefinition }) {
  const { state } = useUniversitySession();
  const location = useLocation();
  if (state.status === 'signed-out')
    return (
      <Navigate
        to={`/auth/login?returnTo=${encodeURIComponent(location.pathname + location.search)}`}
        replace
      />
    );
  if (definition.kind === 'registration-scanner')
    return state.status === 'authorized' && state.membership.role === 'student' ? (
      <AppShell>
        <RegistrationScannerPage />
      </AppShell>
    ) : (
      <main className="system-state-page">
        <RegistrationScannerPage />
      </main>
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
  if (state.membership.role !== definition.role)
    return (
      <main className="system-state-page">
        <section className="system-state">
          <h1>University access unavailable</h1>
          <p>This page requires your university to grant the matching workspace role.</p>
          <Link to="/auth/login">Check access</Link>
        </section>
      </main>
    );
  if (
    ['announcements', 'profile', 'settings'].includes(definition.kind) ||
    (definition.kind === 'notifications' && definition.role !== 'student')
  )
    return (
      <AppShell
        key={`${state.membership.uid}:${state.membership.role}:${state.membership.membership_revision}`}
      >
        {definition.kind === 'announcements' ? (
          <AnnouncementsPage role={definition.role} />
        ) : definition.kind === 'notifications' ? (
          <ConnectedUpdatesPage role={definition.role} />
        ) : (
          <AccountProfilePage role={definition.role} settings={definition.kind === 'settings'} />
        )}
      </AppShell>
    );
  if (definition.role !== 'student')
    return (
      <AppShell
        key={`${state.membership.uid}:${state.membership.role}:${state.membership.membership_revision}`}
      >
        {['rooms', 'room-detail'].includes(definition.kind) ? (
          <ConnectedRoomsPage role={definition.role} detail={definition.kind === 'room-detail'} />
        ) : ['requests', 'request-detail', 'request-create'].includes(definition.kind) ? (
          <ClassroomRequestsPage
            role={definition.role}
            create={definition.kind === 'request-create'}
          />
        ) : definition.role === 'teacher' &&
          ['dashboard', 'schedule', 'calendar', 'notifications'].includes(definition.kind) ? (
          <StructuredCalendarPage role="teacher" dashboard={definition.kind === 'dashboard'} />
        ) : definition.role === 'administrator' &&
          ['dashboard', 'academic-manage'].includes(definition.kind) ? (
          <AcademicManagementPage initialKind={definition.academicKind} />
        ) : definition.role === 'administrator' && definition.kind === 'schedule-create' ? (
          <SchedulingSourcePage />
        ) : definition.role === 'administrator' && definition.kind === 'schedule-drafts' ? (
          <SavedDraftsPage />
        ) : definition.role === 'administrator' && definition.kind === 'schedule-draft-detail' ? (
          <SavedDraftDetailPage />
        ) : definition.role === 'administrator' && definition.kind === 'audit' ? (
          <PublicationAuditPage />
        ) : definition.role === 'administrator' &&
          ['conflicts', 'conflict-detail'].includes(definition.kind) ? (
          <ConflictCenterPage />
        ) : definition.role === 'administrator' &&
          ['calendar', 'schedule'].includes(definition.kind) ? (
          <>
            <nav aria-label="Schedule management" className="draft-actions">
              <Link className="button" to="/admin/schedule-manager/create">
                Generate timetable
              </Link>
              <Link
                className="button button--secondary"
                to="/admin/schedule-manager/drafts?source=academic"
              >
                Review drafts
              </Link>
              <Link to="/admin/academic">Manage academic inputs</Link>
            </nav>
            <StructuredCalendarPage role="administrator" />
          </>
        ) : (
          <section className="workspace-card">
            <h1>This service is not connected</h1>
            <Link to="/auth/login">Return to your account</Link>
          </section>
        )}
      </AppShell>
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
        <StudentRooms key={definition.id} detail={definition.kind === 'room-detail'} />
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
  if (!capabilities.previewRoles) return <ConnectedUniversityRoute definition={definition} />;
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
  if (definition.kind === 'registration-scanner')
    return (
      <AppShell>
        <RegistrationScannerPage />
      </AppShell>
    );
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
