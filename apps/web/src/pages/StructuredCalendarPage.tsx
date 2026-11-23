import { lazy, Suspense } from 'react';
import type { UserRole } from '../types/ui';
const StudentSchedule = lazy(() =>
  import('./StudentSchedule').then((module) => ({ default: module.StudentSchedule })),
);
const Workspace = lazy(() =>
  import('./RoleScheduleWorkspace').then((module) => ({ default: module.RoleScheduleWorkspace })),
);
export function StructuredCalendarPage(props: { role: UserRole; dashboard?: boolean }) {
  if (props.role === 'student' && !props.dashboard)
    return (
      <Suspense fallback={<p role="status">Opening your schedule…</p>}>
        <StudentSchedule />
      </Suspense>
    );
  return (
    <Suspense fallback={<p role="status">Opening your schedule…</p>}>
      <Workspace {...props} />
    </Suspense>
  );
}
