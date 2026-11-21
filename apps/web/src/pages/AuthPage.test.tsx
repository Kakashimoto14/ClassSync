import { render, screen } from '@testing-library/react';
import { DevelopmentRoleProvider } from '../auth/DevelopmentRoleProvider';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthPage } from './AuthPage';
import { UniversitySessionContext } from '../auth/university-session-context';

vi.mock('../auth/TurnstileWidget', () => ({
  TurnstileWidget: () => <div aria-label="Human verification" />,
}));

beforeEach(() => sessionStorage.clear());

describe('honest sign-in entry', () => {
  it('always shows the real sign-in form at /auth/login, even with a preview session', () => {
    sessionStorage.setItem('classsync.preview.v1', JSON.stringify({
      version: 1, role: 'administrator', startedAt: Date.now(),
    }));
    render(
      <MemoryRouter initialEntries={['/auth/login?returnTo=%2Fteacher%2Fschedule']}>
        <UniversitySessionContext.Provider value={{
          available: true,
          state: { status: 'signed-out' },
          refresh: vi.fn(),
          signOut: vi.fn(),
        }}>
          <DevelopmentRoleProvider><AuthPage /></DevelopmentRoleProvider>
        </UniversitySessionContext.Provider>
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'Welcome to ClassSync' })).toBeInTheDocument();
    expect(screen.getByLabelText('Student Number or Email')).toBeInTheDocument();
    expect(screen.getByLabelText('Password')).toBeInTheDocument();
    expect(screen.getByLabelText('Human verification')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign in to ClassSync →' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue with Google' })).toBeInTheDocument();
    expect(screen.getAllByText('Signing in for the first time?')).toHaveLength(2);
    expect(screen.queryByText('Explore ClassSync')).not.toBeInTheDocument();
    expect(screen.queryByText('Sample preview · You are not signed in.')).not.toBeInTheDocument();
  });
  it('provides sample navigation without requesting credentials or live identity', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    try {
      render(
        <MemoryRouter>
          <DevelopmentRoleProvider>
            <AuthPage />
          </DevelopmentRoleProvider>
        </MemoryRouter>,
      );
      expect(screen.getByRole('link', { name: 'Explore ClassSync' })).toHaveAttribute(
        'href',
        '/dev/role-preview',
      );
      expect(screen.getByText('Sample preview · You are not signed in.')).toBeInTheDocument();
      expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
      expect(fetchSpy).not.toHaveBeenCalled();
    } finally {
      fetchSpy.mockRestore();
    }
  });
});
