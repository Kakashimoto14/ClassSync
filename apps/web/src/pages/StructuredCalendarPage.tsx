import { lazy, Suspense } from 'react';
import { StudentSchedule } from './StudentSchedule';
import type { UserRole } from '../types/ui';
const Workspace = lazy(() =>
  import('./RoleScheduleWorkspace').then((module) => ({ default: module.RoleScheduleWorkspace })),
);
export function StructuredCalendarPage(props: { role: UserRole; dashboard?: boolean }) {
  if (props.role === 'student' && !props.dashboard) return <StudentSchedule />;
  return (
    <Suspense fallback={<p role="status">Opening your schedule…</p>}>
      <Workspace {...props} />
    </Suspense>
  );
}
