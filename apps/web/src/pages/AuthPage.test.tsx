import { fireEvent, render, screen } from '@testing-library/react';
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
  it('focuses the first invalid field and links its error', () => {
    render(
      <MemoryRouter>
        <DevelopmentRoleProvider>
          <AuthPage />
        </DevelopmentRoleProvider>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByText('University sign-in'));
    fireEvent.click(screen.getByRole('button', { name: 'Check sign-in availability' }));
    expect(screen.getByLabelText('University email')).toHaveFocus();
    expect(screen.getByLabelText('University email')).toHaveAttribute(
      'aria-describedby',
      'email-error',
    );
    fireEvent.change(screen.getByLabelText('University email'), {
      target: { value: 'sample@example.edu' },
    });
    expect(screen.queryByText('Enter your university email address.')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Check sign-in availability' }));
    expect(screen.getByLabelText('Password')).toHaveFocus();
  });
  it('reveals the password accessibly and never simulates a successful connection', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    try {
      render(
        <MemoryRouter initialEntries={['/auth/login?returnTo=%2Fteacher%2Fschedule']}>
          <DevelopmentRoleProvider>
            <AuthPage />
          </DevelopmentRoleProvider>
        </MemoryRouter>,
      );
      fireEvent.click(screen.getByText('University sign-in'));
      fireEvent.change(screen.getByLabelText('University email'), {
        target: { value: 'sample@example.edu' },
      });
      fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'example-only' } });
      fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
      expect(screen.getByLabelText('Password')).toHaveAttribute('type', 'text');
      expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
      fireEvent.click(screen.getByRole('button', { name: 'Check sign-in availability' }));
      expect(screen.getByText('Sign-in unavailable')).toBeInTheDocument();
      expect(screen.queryByText(/Connecting/)).not.toBeInTheDocument();
      expect(fetchSpy).not.toHaveBeenCalled();
      expect(screen.getByRole('link', { name: 'Explore ClassSync' })).toHaveAttribute(
        'href',
        '/dev/role-preview?returnTo=%2Fteacher%2Fschedule',
      );
    } finally {
      fetchSpy.mockRestore();
    }
  });
});
