import { useEffect, useRef } from 'react';
import { Link, useLocation, useInRouterContext } from 'react-router-dom';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { useUniversitySession } from './university-session-context';
import { workspaceDestination } from './access';
import type { UserRole } from '../types/ui';

const names: Record<UserRole, string> = {
  student: 'Student',
  teacher: 'Teacher',
  administrator: 'Administrator',
};
const messages = {
  checking: ['Checking university access', 'We’re checking your current membership.'],
  'signed-out': ['Signed out', 'Sign in to continue.'],
  'role-required': [
    'Choose a workspace',
    'Your university has granted access to more than one workspace.',
  ],
  'verification-required': [
    'Email verification required',
    'Use the link in your inbox to verify your email.',
  ],
  expired: ['Session expired', 'Sign out, then sign in again to continue.'],
  denied: [
    'University access is not active',
    'If you have a university account, check your setup or contact your university.',
  ],
  unavailable: ['Access check unavailable', 'Try again to confirm your current membership.'],
  offline: ['You are offline', 'Reconnect to check your university access.'],
} as const;

function WorkspaceLink({ role }: { role: UserRole }) {
  const { search } = useLocation();
  return (
    <Link
      className="button"
      to={workspaceDestination(role, new URLSearchParams(search).get('returnTo'))}
    >
      Open {names[role]} workspace
    </Link>
  );
}

export function UniversitySessionPanel() {
  const inRouter = useInRouterContext();
  const { state, refresh, signOut } = useUniversitySession();
  const section = useRef<HTMLElement>(null);
  const exiting = useRef(false);
  const choosing = useRef(false);
  useEffect(() => {
    if (
      (exiting.current && state.status === 'signed-out') ||
      (choosing.current && state.status !== 'checking')
    ) {
      section.current?.focus();
      exiting.current = false;
      choosing.current = false;
    }
  }, [state.status]);

  const roles =
    state.status === 'role-required'
      ? state.availableRoles
      : state.status === 'authorized'
        ? state.membership.available_roles
        : undefined;
  const [title, message] =
    state.status === 'authorized'
      ? [
          names[state.membership.role] + ' membership verified',
          'Your identity and current university role are verified.',
        ]
      : messages[state.status];

  return (
    <section
      className="university-session"
      aria-label="University access"
      ref={section}
      tabIndex={-1}
    >
      <Alert tone={state.status === 'authorized' ? 'success' : 'info'} title={title}>
        {message}
      </Alert>
      {state.status === 'authorized' && inRouter && <WorkspaceLink role={state.membership.role} />}
      {roles && roles.length > 1 && (
        <fieldset className="university-session__roles">
          <legend>Available workspaces</legend>
          {roles.map((role) => (
            <Button
              key={role}
              variant="secondary"
              aria-pressed={state.status === 'authorized' && state.membership.role === role}
              onClick={() => {
                choosing.current = true;
                refresh(role);
              }}
            >
              {names[role]}
            </Button>
          ))}
        </fieldset>
      )}
      {state.status !== 'signed-out' && (
        <div className="university-session__actions">
          {(state.status === 'denied' || state.status === 'unavailable') && (
            <Button variant="secondary" onClick={() => refresh()}>
              Retry access check
            </Button>
          )}
          <Button
            variant="ghost"
            onClick={() => {
              exiting.current = true;
              signOut();
            }}
          >
            Sign out
          </Button>
        </div>
      )}
    </section>
  );
}
