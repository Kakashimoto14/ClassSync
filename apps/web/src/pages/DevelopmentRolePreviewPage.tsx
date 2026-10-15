import { ClassSyncLogo } from '../components/brand/ClassSyncLogo';
import { useDevelopmentRole } from '../auth/useDevelopmentRole';
import { Button } from '../components/ui/Button';
import type { UserRole } from '../types/ui';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { demoDestination } from '../auth/access';
import { previewContext } from '../data/schedule-preview';

export function DevelopmentRolePreviewPage() {
  const { role, startDemo } = useDevelopmentRole();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const options: UserRole[] = ['student', 'teacher', 'administrator'];
  const requestedPath = searchParams.get('returnTo');
  const openDemo = (selectedRole: UserRole) => {
    startDemo(selectedRole);
    navigate(demoDestination(selectedRole, requestedPath), { replace: true });
  };
  return (
    <main className="system-state-page">
      <section className="workspace-card role-preview-card">
        <ClassSyncLogo />
        <p className="eyebrow">Development-only access</p>
        <h1>Choose a demo workspace</h1>
        <p>Sample workspaces only. This does not sign you in or grant production permissions.</p>
        <p className="muted">
          Dashboard scenario: {previewContext.label}. The preview clears on refresh.
        </p>
        <div className="demo-role-options">
          {options.map((option) => (
            <Button
              key={option}
              variant={role === option ? 'primary' : 'secondary'}
              onClick={() => openDemo(option)}
            >
              Open {option} demo
            </Button>
          ))}
        </div>
        <Link className="text-action" to="/auth/login">
          Return to sign in
        </Link>
      </section>
    </main>
  );
}
