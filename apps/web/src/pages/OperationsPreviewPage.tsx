import { useDevelopmentRole } from '../auth/useDevelopmentRole';
import { AppShell } from '../components/layout/AppShell';
import { AdminSchedulingHome } from './AdminSchedulingHome';
import { StructuredCalendarPage } from './StructuredCalendarPage';

export function OperationsPreviewPage() {
  const { role } = useDevelopmentRole();
  if (!role) return null;
  return (
    <AppShell>
      <div className="dashboard">
        {role === 'student' && <StructuredCalendarPage role={role} dashboard />}
        {role === 'teacher' && <StructuredCalendarPage role={role} dashboard />}
        {role === 'administrator' && <AdminSchedulingHome />}
      </div>
    </AppShell>
  );
}
