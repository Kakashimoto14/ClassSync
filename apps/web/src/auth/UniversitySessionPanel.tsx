import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import { useUniversitySession } from './university-session-context';
import { Link, useLocation, useInRouterContext } from 'react-router-dom';

function StudentWorkspaceLink() {
  const location = useLocation();
  const target = new URLSearchParams(location.search).get('returnTo');
  return (
    <Link
      className="button"
      to={
        target && /^\/student\/(dashboard|schedule|calendar|rooms)(\?|$)/.test(target)
          ? target
          : '/student/dashboard'
      }
    >
      Open Student workspace
    </Link>
  );
}

const roles = [
  ['student', 'Student'],
  ['teacher', 'Teacher'],
  ['administrator', 'Administrator'],
] as const;
const messages = {
  checking: ['Checking university access', 'Verifying your identity and current membership.'],
  'signed-out': ['Signed out', 'Sign in below to check your current university access.'],
  'role-required': [
    'Choose a role to verify',
    'Only roles granted by your university can be used.',
  ],
  denied: [
    'Current membership required',
    'Access could not be verified. Check another role or contact your university.',
  ],
  unavailable: [
    'Access check unavailable',
    'Access is hidden until your current membership can be checked. Retry or sign out.',
  ],
  offline: [
    'You are offline',
    'Access is hidden until your connection returns and current membership is checked again.',
  ],
} as const;

export function UniversitySessionPanel() {
  const inRouter = useInRouterContext();
  const { state, refresh, signOut } = useUniversitySession();
  const section = useRef<HTMLElement>(null);
  const exiting = useRef(false);
  useEffect(() => {
    if (exiting.current && state.status === 'signed-out') {
      section.current?.focus();
      exiting.current = false;
    }
  }, [state.status]);
  const checking = state.status === 'checking';
  const roleDisabled = checking || state.status === 'offline';
  const authorized = state.status === 'authorized';
  const [title, message] = authorized
    ? [
        `${roles.find(([role]) => role === state.membership.role)?.[1]} membership verified`,
        state.membership.role === 'student'
          ? 'Your identity and current Student role are verified.'
          : 'Your identity and current role are verified. Connected schedules are not available yet.',
      ]
    : messages[state.status];
  return (
    <section
      className="university-session"
      aria-label="University access"
      ref={section}
      tabIndex={-1}
    >
      <Alert
        tone={authorized ? 'success' : state.status === 'denied' ? 'danger' : 'info'}
        title={title}
      >
        {message}
      </Alert>
      {authorized && state.membership.role === 'student' && inRouter && <StudentWorkspaceLink />}
      {state.status !== 'signed-out' && (
        <fieldset className="university-session__roles" aria-busy={checking}>
          <legend>Check a workspace role</legend>
          {roles.map(([role, label]) => (
            <Button
              key={role}
              variant="secondary"
              aria-pressed={authorized && state.membership.role === role}
              aria-disabled={roleDisabled}
              onClick={() => {
                if (!roleDisabled) refresh(role);
              }}
            >
              Check {label} access
            </Button>
          ))}
        </fieldset>
      )}
      {state.status !== 'signed-out' && (
        <div className="university-session__actions">
          <Button
            variant="secondary"
            aria-disabled={checking}
            onClick={() => {
              if (!checking) refresh();
            }}
          >
            Retry access check
          </Button>
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
import { useEffect, useRef } from 'react';
