import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { PasswordStrengthChecklist } from './PasswordStrengthChecklist';

it('reports six unmet requirements as incomplete, then updates each requirement live', () => {
  const { rerender } = render(
    <PasswordStrengthChecklist password="" confirmPassword="" />,
  );
  expect(screen.getByRole('list', { name: 'Password requirements' }).children).toHaveLength(6);
  expect(screen.getByText('At least 12 characters').closest('li')).toHaveAttribute('data-complete', 'false');
  expect(screen.getByText('Uppercase letter (A–Z)').closest('li')).toHaveAttribute('data-complete', 'false');
  rerender(
    <PasswordStrengthChecklist password="Campus-pass-26!" confirmPassword="Campus-pass-26!" />,
  );
  for (const rule of [
    'At least 12 characters', 'Uppercase letter (A–Z)', 'Lowercase letter (a–z)',
    'Number (0–9)', 'Special character (!@#$...)', 'Passwords match',
  ]) expect(screen.getByText(rule).closest('li')).toHaveAttribute('data-complete', 'true');
});

it('keeps the match requirement incomplete until confirmation is entered', () => {
  const { rerender } = render(
    <PasswordStrengthChecklist password="Campus-pass-26!" confirmPassword="" />,
  );
  expect(screen.getByText('Passwords match').closest('li')).toHaveAttribute('data-complete', 'false');
  rerender(
    <PasswordStrengthChecklist password="Campus-pass-26!" confirmPassword="different" />,
  );
  expect(screen.getByText('Passwords match').closest('li')).toHaveAttribute('data-complete', 'false');
});
