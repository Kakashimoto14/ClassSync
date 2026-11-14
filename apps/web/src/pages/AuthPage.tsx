import { Link, useSearchParams } from 'react-router-dom';
import { demoDestination } from '../auth/access';
import { useDevelopmentRole } from '../auth/useDevelopmentRole';
import { appMode } from '../config/runtime-config';
import { EntranceLayout, InstitutionalEntrance } from './InstitutionalEntrance';

export function AuthPage() {
  return appMode === 'institutional' ? <InstitutionalEntrance /> : <SampleEntrance />;
}

function SampleEntrance() {
  const { role } = useDevelopmentRole();
  const [searchParams] = useSearchParams();
  const requested = searchParams.get('returnTo');
  const demoHref = requested
    ? '/dev/role-preview?returnTo=' + encodeURIComponent(requested)
    : '/dev/role-preview';

  return (
    <EntranceLayout>
      <h1>{role ? 'Welcome back' : 'Explore ClassSync'}</h1>
      <p className="connected-entrance__intro">
        See how schedules, classrooms, and updates fit together.
      </p>
      <Link className="button" to={role ? demoDestination(role, requested) : demoHref}>
        {role ? 'Continue to workspace' : 'Explore ClassSync'}
      </Link>
      <p className="connected-entrance__secondary">Sample preview · You are not signed in.</p>
      {role && <Link to={demoHref}>Choose another role</Link>}
    </EntranceLayout>
  );
}
