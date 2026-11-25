import { lazy, Suspense } from 'react';
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom';
import { DevelopmentRoleProvider } from '../auth/DevelopmentRoleProvider';
import { useDevelopmentRole } from '../auth/useDevelopmentRole';
import { AppShell } from '../components/layout/AppShell';
import { dashboardPath } from './route-config';
import type { RouteDefinition } from './route-config';
import { capabilities } from '../config/runtime-config';
import { UniversitySessionProvider } from '../auth/UniversitySessionProvider';
import { useUniversitySession } from '../auth/university-session-context';
import { UniversitySessionPanel } from '../auth/UniversitySessionPanel';
import type { ReactNode } from 'react';
import { ClassSyncPageLoader } from '../components/loading/ClassSyncLoading';

const OperationsPreviewPage = lazy(() =>
  import('../pages/OperationsPreviewPage').then((module) => ({ default: module.OperationsPreviewPage })),
);
const ComingSoonPage = lazy(() =>
  import('../pages/ComingSoonPage').then((module) => ({ default: module.ComingSoonPage })),
);
const ProductScreenPage = lazy(() =>
  import('../pages/ProductScreenPage').then((module) => ({ default: module.ProductScreenPage })),
);
const StudentHome = lazy(() =>
  import('../pages/StudentHome').then((module) => ({ default: module.StudentHome })),
);
const StudentRooms = lazy(() =>
  import('../pages/StudentRooms').then((module) => ({ default: module.StudentRooms })),
);
const StructuredCalendarPage = lazy(() =>
  import('../pages/StructuredCalendarPage').then((module) => ({ default: module.StructuredCalendarPage })),
);
const RegistrationScannerPage = lazy(() =>
  import('../pages/RegistrationScannerPage').then((module) => ({ default: module.RegistrationScannerPage })),
);
const AcademicManagementPage = lazy(() =>
  import('../pages/AcademicManagementPage').then((module) => ({ default: module.AcademicManagementPage })),
);
const SchedulingSourcePage = lazy(() =>
  import('../pages/AcademicGenerationPage').then((module) => ({ default: module.SchedulingSourcePage })),
);
const SavedDraftsPage = lazy(() =>
  import('../pages/SchedulingDraftPages').then((module) => ({ default: module.SavedDraftsPage })),
);
const SavedDraftDetailPage = lazy(() =>
  import('../pages/SchedulingDraftPages').then((module) => ({ default: module.SavedDraftDetailPage })),
);
const PublicationAuditPage = lazy(() =>
  import('../pages/PublicationAuditPage').then((module) => ({ default: module.PublicationAuditPage })),
);
const ConflictCenterPage = lazy(() =>
  import('../pages/ConflictCenterPage').then((module) => ({ default: module.ConflictCenterPage })),
);
const ClassroomRequestsPage = lazy(() =>
  import('../pages/ClassroomRequestsPage').then((module) => ({ default: module.ClassroomRequestsPage })),
);
const ConnectedRoomsPage = lazy(() =>
  import('../pages/ConnectedRoomsPage').then((module) => ({ default: module.ConnectedRoomsPage })),
);
const AnnouncementsPage = lazy(() =>
  import('../pages/AnnouncementsPage').then((module) => ({ default: module.AnnouncementsPage })),
);
const AccountProfilePage = lazy(() =>
  import('../pages/AccountProfilePage').then((module) => ({ default: module.AccountProfilePage })),
);
const ConnectedUpdatesPage = lazy(() =>
  import('../pages/ConnectedUpdatesPage').then((module) => ({ default: module.ConnectedUpdatesPage })),
);

function RouteLoading() {
  return <ClassSyncPageLoader label="Loading your workspace…" />;
}

function LazyPage({ children }: { children: ReactNode }) {
  return <Suspense fallback={<RouteLoading />}>{children}</Suspense>;
}

function ConnectedUniversityRoute({ definition }: { definition: RouteDefinition }) {
  const { state } = useUniversitySession();
  const location = useLocation();
  if (state.status === 'checking') return <ClassSyncPageLoader label="Checking university access…" />;
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
        <LazyPage><RegistrationScannerPage /></LazyPage>
      </AppShell>
    ) : (
      <main className="system-state-page">
        <LazyPage><RegistrationScannerPage /></LazyPage>
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
        <LazyPage>
          {definition.kind === 'announcements' ? (
            <AnnouncementsPage role={definition.role} />
          ) : definition.kind === 'notifications' ? (
            <ConnectedUpdatesPage role={definition.role} />
          ) : (
            <AccountProfilePage role={definition.role} settings={definition.kind === 'settings'} />
          )}
        </LazyPage>
      </AppShell>
    );
  if (definition.role !== 'student')
    return (
      <AppShell
        key={`${state.membership.uid}:${state.membership.role}:${state.membership.membership_revision}`}
      >
        <LazyPage>
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
        </LazyPage>
      </AppShell>
    );
  return (
    <AppShell>
      <LazyPage>
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
      </LazyPage>
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
  if (definition.kind === 'dashboard') return <LazyPage><OperationsPreviewPage /></LazyPage>;
  if (definition.kind === 'registration-scanner')
    return (
      <AppShell>
        <LazyPage><RegistrationScannerPage /></LazyPage>
      </AppShell>
    );
  if (definition.kind === 'coming-soon' && definition.plannedFeature)
    return (
      <AppShell>
        <LazyPage><ComingSoonPage feature={definition.plannedFeature} role={role} /></LazyPage>
      </AppShell>
    );
  return <LazyPage><ProductScreenPage definition={definition} /></LazyPage>;
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
