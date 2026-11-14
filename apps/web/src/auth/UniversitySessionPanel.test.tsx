import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { UniversitySessionPanel } from './UniversitySessionPanel';
import { UniversitySessionContext } from './university-session-context';
import type { UniversitySession } from './university-session';

describe('university access controls', () => {
  it('restores focus to the signed-out status after an explicit sign-out', () => {
    const signOut = vi.fn();
    const panel = (state: UniversitySession) => (
      <UniversitySessionContext.Provider
        value={{ available: true, state, refresh: vi.fn(), signOut }}
      >
        <UniversitySessionPanel />
      </UniversitySessionContext.Provider>
    );
    const view = render(panel({ status: 'denied' }));
    const button = screen.getByRole('button', { name: 'Sign out' });
    button.focus();
    fireEvent.click(button);
    expect(signOut).toHaveBeenCalledOnce();
    view.rerender(panel({ status: 'signed-out' }));
    expect(screen.getByRole('region', { name: 'University access' })).toHaveFocus();
    expect(screen.getByRole('status')).toHaveTextContent('Signed out');
  });
  it('offers only server-verified workspaces and hides choices while checking access', () => {
    const refresh = vi.fn();
    const panel = (state: UniversitySession) => (
      <UniversitySessionContext.Provider
        value={{ available: true, state, refresh, signOut: vi.fn() }}
      >
        <UniversitySessionPanel />
      </UniversitySessionContext.Provider>
    );
    const view = render(panel({ status: 'role-required', availableRoles: ['student', 'teacher'] }));
    expect(screen.queryByRole('button', { name: 'Administrator' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Teacher' }));
    expect(refresh).toHaveBeenCalledWith('teacher');
    view.rerender(panel({ status: 'checking' }));
    expect(screen.queryByRole('button', { name: 'Teacher' })).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Checking university access');
    view.rerender(
      panel({
        status: 'authorized',
        membership: {
          uid: 'u',
          tenant_id: 't',
          role: 'teacher',
          faculty_id: 'f',
          membership_revision: 2,
          available_roles: ['student', 'teacher'],
        },
      }),
    );
    expect(screen.getByRole('region', { name: 'University access' })).toHaveFocus();
    expect(screen.getByRole('button', { name: 'Teacher' })).toHaveAttribute('aria-pressed', 'true');
  });
  it.each(['denied', 'unavailable', 'offline'] as const)(
    'does not show prior membership during %s',
    (status) => {
      render(
        <UniversitySessionContext.Provider
          value={{ available: true, state: { status }, refresh: vi.fn(), signOut: vi.fn() }}
        >
          <UniversitySessionPanel />
        </UniversitySessionContext.Provider>,
      );
      expect(screen.queryByText(/membership verified/)).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
    },
  );
});
