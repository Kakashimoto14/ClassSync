import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { AuthPage } from './AuthPage';

describe('honest sign-in entry', () => {
  it('focuses the first invalid field and links its error', () => {
    render(
      <MemoryRouter>
        <AuthPage />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByText('University sign-in'));
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByLabelText('University email')).toHaveFocus();
    expect(screen.getByLabelText('University email')).toHaveAttribute(
      'aria-describedby',
      'email-error',
    );
    fireEvent.change(screen.getByLabelText('University email'), {
      target: { value: 'sample@example.edu' },
    });
    expect(screen.queryByText('Enter your university email address.')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByLabelText('Password')).toHaveFocus();
  });
  it('reveals the password accessibly and never simulates a successful connection', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    try {
      render(
        <MemoryRouter initialEntries={['/auth/login?returnTo=%2Fteacher%2Fschedule']}>
          <AuthPage />
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
      fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
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
