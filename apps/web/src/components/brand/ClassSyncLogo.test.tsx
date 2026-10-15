import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ClassSyncLogo } from './ClassSyncLogo';

describe('ClassSync branding while approved ribbon exports are unavailable', () => {
  it.each(['horizontal', 'full', 'symbol'] as const)(
    'uses an honest text fallback for %s',
    (variant) => {
      const { container } = render(<ClassSyncLogo variant={variant} />);
      expect(screen.getByText('ClassSync')).toBeInTheDocument();
      expect(container.querySelector('[data-logo-asset="pending"]')).toBeInTheDocument();
      expect(container.querySelector('img, svg')).not.toBeInTheDocument();
      expect(Boolean(screen.queryByText('Smarter Classrooms Together'))).toBe(variant === 'full');
    },
  );

  it('supports a dark surface and a decorative label inside a named home link', () => {
    const { container } = render(
      <a href="/" aria-label="ClassSync home">
        <ClassSyncLogo surface="dark" decorative />
      </a>,
    );
    expect(screen.getByRole('link', { name: 'ClassSync home' })).toBeInTheDocument();
    expect(container.querySelector('.classsync-logo--dark')).toHaveAttribute('aria-hidden', 'true');
  });
});
