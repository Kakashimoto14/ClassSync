import { lazy, Suspense } from 'react';
import type { RouteDefinition } from '../routes/route-config';
import { ClassSyncPageLoader } from '../components/loading/ClassSyncLoading';

// Nested lazy imports keep these pages' preload lists out of the main entry.
const BuildingsPage = lazy(() =>
  import('./BuildingsPage').then((module) => ({ default: module.BuildingsPage })),
);
const ReportsPage = lazy(() =>
  import('./ReportsPage').then((module) => ({ default: module.ReportsPage })),
);
const TeacherIssueReportPage = lazy(() =>
  import('./TeacherIssueReportPage').then((module) => ({
    default: module.TeacherIssueReportPage,
  })),
);

export function ConnectedOperationsPage({ definition }: { definition: RouteDefinition }) {
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{definition.title}</h1>
        </div>
      </div>
      <Suspense fallback={<ClassSyncPageLoader label="Loading this page…" />}>
        {definition.kind === 'report-issue' ? (
          <TeacherIssueReportPage />
        ) : definition.kind === 'reports' ? (
          <ReportsPage key={definition.id} utilization={definition.id.endsWith('.utilization')} />
        ) : (
          <BuildingsPage key={definition.id} detail={definition.kind === 'building-detail'} />
        )}
      </Suspense>
    </>
  );
}
