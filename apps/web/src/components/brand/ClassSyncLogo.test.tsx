import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ClassSyncLogo } from './ClassSyncLogo';

describe('supplied provisional raster branding', () => {
  it.each([
    ['horizontal', 'classsync-horizontal-light.png'],
    ['full', 'classsync-horizontal-light.png'],
    ['symbol', 'classsync-ribbon-mark.png'],
  ] as const)('loads %s artwork without duplicate visible labels', (variant, file) => {
    const { container } = render(<ClassSyncLogo variant={variant} />);
    expect(screen.getByRole('img', { name: 'ClassSync' })).toHaveAttribute(
      'src',
      '/branding/classsync-logo-assets/' + file,
    );
    expect(container.querySelector('[data-logo-asset="provisional-raster"]')).toBeInTheDocument();
    expect(screen.queryByText('ClassSync')).not.toBeInTheDocument();
    expect(screen.queryByText('Smarter Classrooms Together')).not.toBeInTheDocument();
    if (variant === 'full') {
      expect(container.querySelector('source')).toHaveAttribute('media', '(min-width: 1280px)');
      expect(container.querySelector('source')).toHaveAttribute(
        'srcset',
        '/branding/classsync-logo-assets/classsync-full-light.png',
      );
    }
  });
  it.each(['horizontal', 'full', 'symbol'] as const)(
    'replaces a broken %s image with accessible text',
    (variant) => {
      const { container } = render(<ClassSyncLogo variant={variant} />);
      fireEvent.error(screen.getByRole('img', { name: 'ClassSync' }));
      expect(screen.getByText('ClassSync')).toBeInTheDocument();
      expect(container.querySelector('img, picture')).not.toBeInTheDocument();
      expect(container.querySelector('[data-logo-asset="fallback"]')).toBeInTheDocument();
      expect(Boolean(screen.queryByText('Smarter Classrooms Together'))).toBe(variant === 'full');
    },
  );
  it('keeps decorative artwork inside a named home link accessible through the link', () => {
    const { container } = render(
      <a href="/" aria-label="ClassSync home">
        <ClassSyncLogo surface="dark" decorative />
      </a>,
    );
    expect(screen.getByRole('link', { name: 'ClassSync home' })).toBeInTheDocument();
    expect(container.querySelector('.classsync-logo--dark')).toHaveAttribute('aria-hidden', 'true');
    expect(container.querySelector('img')).toHaveAttribute('alt', '');
    fireEvent.error(container.querySelector('img')!);
    expect(screen.getByRole('link', { name: 'ClassSync home' })).toBeInTheDocument();
    expect(container.querySelector('.classsync-logo--dark')).toHaveAttribute('aria-hidden', 'true');
  });
});
