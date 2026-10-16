import { useDevelopmentRole } from '../auth/useDevelopmentRole';
import { AppShell } from '../components/layout/AppShell';
import { previewContext, schedulePreview } from '../data/schedule-preview';
import { StudentDashboard } from './dashboards/StudentDashboard';
import { TeacherDashboard } from './dashboards/TeacherDashboard';
import { AdministratorDashboard } from './dashboards/AdministratorDashboard';

export function OperationsPreviewPage() {
  const { role } = useDevelopmentRole();
  if (!role) return null;
  return (
    <AppShell>
      <div className="dashboard">
        {role !== 'student' && (
          <div className="preview-context">
            <strong>Sample day · {previewContext.label}</strong>
            <span>Fixed local demo time, not a live schedule or institutional timezone.</span>
          </div>
        )}
        {role === 'student' && <StudentDashboard data={schedulePreview} />}
        {role === 'teacher' && <TeacherDashboard data={schedulePreview} />}
        {role === 'administrator' && <AdministratorDashboard data={schedulePreview} />}
      </div>
    </AppShell>
  );
}
