import { ArrowRight, BookOpen, GraduationCap, CalendarDays } from 'lucide-react';
import { ClassSyncLogo } from '../components/brand/ClassSyncLogo';
import { useDevelopmentRole } from '../auth/useDevelopmentRole';
import { Button } from '../components/ui/Button';
import type { UserRole } from '../types/ui';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { demoDestination } from '../auth/access';
import { previewEnabled } from '../auth/preview-session';
import { dashboardPath } from '../routes/route-config';

export function DevelopmentRolePreviewPage() {
  const { role, startDemo } = useDevelopmentRole();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const options = [
    {
      role: 'student',
      title: 'Student',
      detail: 'Your next class, schedule, and classroom.',
      Icon: GraduationCap,
    },
    {
      role: 'teacher',
      title: 'Teacher',
      detail: 'Teaching assignments and room change requests.',
      Icon: BookOpen,
    },
    {
      role: 'administrator',
      title: 'Administrator',
      detail: 'Scheduling issues, decisions, and campus resources.',
      Icon: CalendarDays,
    },
  ] as const;
  const requestedPath = searchParams.get('returnTo');
  if (!previewEnabled) return <Navigate to="/auth/login" replace />;
  const openDemo = (selectedRole: UserRole) => {
    startDemo(selectedRole);
    navigate(demoDestination(selectedRole, requestedPath), { replace: true });
  };
  return (
    <main className="system-state-page">
      <section className="workspace-card role-preview-card">
        <ClassSyncLogo />

        <h1>Choose your workspace</h1>
        <p>Choose a role to explore sample schedules and CDM spaces.</p>
        {role && (
          <Link className="text-action" to={dashboardPath(role)}>
            Continue {role} preview
          </Link>
        )}
        <div className="demo-role-options">
          {options.map(({ role: option, title, detail, Icon }) => (
            <Button
              className="role-option"
              key={option}
              variant={role === option ? 'primary' : 'secondary'}
              aria-label={`Open ${option} demo`}
              onClick={() => openDemo(option)}
            >
              <Icon size={24} aria-hidden="true" />
              <span>
                <strong>{title}</strong>
                <span>{detail}</span>
              </span>
              <ArrowRight size={18} aria-hidden="true" />
            </Button>
          ))}
        </div>
        <details className="preview-session-note">
          <summary>About preview access</summary>
          <p className="muted">
            Sample preview only; no account is authenticated. Your selection survives refresh in
            this tab for up to 8 hours. Exit demo clears it. CDM spaces are provisional.
          </p>
        </details>
        <Link className="text-action" to="/auth/login">
          Return to sign in
        </Link>
      </section>
    </main>
  );
}
