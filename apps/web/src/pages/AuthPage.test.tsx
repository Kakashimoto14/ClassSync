import { render, screen } from '@testing-library/react';
import { DevelopmentRoleProvider } from '../auth/DevelopmentRoleProvider';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthPage } from './AuthPage';
import { previewSessionKey } from '../auth/preview-session';

beforeEach(() => sessionStorage.clear());

describe('honest sign-in entry', () => {
  it.each([
    ['teacher', '/teacher/schedule'],
    ['student', '/student/dashboard'],
    ['administrator', '/admin/dashboard'],
  ])('continues a valid %s session only to a role-owned destination', (role, destination) => {
    sessionStorage.setItem(
      previewSessionKey,
      JSON.stringify({ version: 1, role, startedAt: Date.now() }),
    );
    render(
      <MemoryRouter initialEntries={['/auth/login?returnTo=%2Fteacher%2Fschedule']}>
        <DevelopmentRoleProvider>
          <AuthPage />
        </DevelopmentRoleProvider>
      </MemoryRouter>,
    );
    expect(screen.getByRole('link', { name: 'Continue to workspace' })).toHaveAttribute(
      'href',
      destination,
    );
    expect(screen.getByRole('link', { name: 'Choose another role' })).toHaveAttribute(
      'href',
      '/dev/role-preview?returnTo=%2Fteacher%2Fschedule',
    );
    expect(screen.queryByRole('link', { name: 'Explore ClassSync' })).not.toBeInTheDocument();
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
