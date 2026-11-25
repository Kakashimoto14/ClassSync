import { lazy, Suspense } from 'react';
import type { UserRole } from '../types/ui';
import { ClassSyncPageLoader } from '../components/loading/ClassSyncLoading';
const StudentSchedule = lazy(() =>
  import('./StudentSchedule').then((module) => ({ default: module.StudentSchedule })),
);
const Workspace = lazy(() =>
  import('./RoleScheduleWorkspace').then((module) => ({ default: module.RoleScheduleWorkspace })),
);
export function StructuredCalendarPage(props: { role: UserRole; dashboard?: boolean }) {
  if (props.role === 'student' && !props.dashboard)
    return (
      <Suspense fallback={<ClassSyncPageLoader label="Loading class schedule…" />}>
        <StudentSchedule />
      </Suspense>
    );
  return (
    <Suspense fallback={<ClassSyncPageLoader label="Loading class schedule…" />}>
      <Workspace {...props} />
    </Suspense>
  );
}
