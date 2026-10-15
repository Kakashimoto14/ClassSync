import { Link } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { useDevelopmentRole } from '../auth/useDevelopmentRole';
import { dashboardPath } from '../routes/route-config';
export function NotFoundPage() {
  const { role } = useDevelopmentRole();
  return (
    <main className="system-state-page">
      <section className="system-state">
        <Compass size={34} aria-hidden="true" />
        <p className="eyebrow">ClassSync</p>
        <h1>We could not find that page.</h1>
        <p>The link may be out of date, or this area may not be available for your role.</p>
        <Link className="button" to={role ? dashboardPath(role) : '/auth/login'}>
          {role ? 'Return to dashboard' : 'Return to sign in'}
        </Link>
      </section>
    </main>
  );
}
