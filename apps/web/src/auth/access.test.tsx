import { act, render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { demoDestination, isRoleOwnedPath, validateLogin } from './access';
import { DevelopmentRoleProvider } from './DevelopmentRoleProvider';
import { useDevelopmentRole } from './useDevelopmentRole';
import type { DevelopmentRoleContextValue } from './development-role-context';

describe('authentication entry and demo access', () => {
  it('validates required login credentials before any authentication attempt', () => {
    expect(validateLogin('', '')).toEqual({ email: 'Enter your university email address.', password: 'Enter your password.' });
    expect(validateLogin('not-an-email', 'password')).toEqual({ email: 'Enter a valid email address.' });
    expect(validateLogin('student@university.edu', 'password')).toEqual({});
  });

  it('sends demo roles only to routes they own', () => {
    expect(demoDestination('teacher', '/teacher/schedule')).toBe('/teacher/schedule');
    expect(demoDestination('student', '/admin/schedule-manager')).toBe('/student/dashboard');
    expect(isRoleOwnedPath('administrator', '/admin/schedule-manager')).toBe(true);
    expect(isRoleOwnedPath('teacher', '/admin/schedule-manager')).toBe(false);
  });

  it('starts and clears the in-memory demo session without persistence', () => {
    let session: DevelopmentRoleContextValue | undefined;
    function Probe() { session = useDevelopmentRole(); return null; }
    render(<DevelopmentRoleProvider><Probe/></DevelopmentRoleProvider>);
    expect(session?.role).toBeNull();
    act(() => session?.startDemo('administrator'));
    expect(session?.role).toBe('administrator');
    act(() => session?.signOut());
    expect(session?.role).toBeNull();
  });
});
