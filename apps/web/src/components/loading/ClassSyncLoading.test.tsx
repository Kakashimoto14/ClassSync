import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ClassSyncPageLoader, ClassSyncSkeleton } from './ClassSyncLoading';

describe('ClassSync loading states', () => {
  afterEach(() => vi.useRealTimers());

  it('announces the current page and shows the calm cold-start message after four seconds', () => {
    vi.useFakeTimers();
    render(<ClassSyncPageLoader label="Loading class schedule…" />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
    expect(screen.getByText('Loading class schedule…')).toBeInTheDocument();
    expect(screen.queryByText(/Waking ClassSync services/)).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(4000));
    expect(screen.getByText('Waking ClassSync services — this takes a few seconds on first load.')).toBeInTheDocument();
  });

  it('renders the requested lightweight skeleton layout accessibly', () => {
    const { container } = render(<ClassSyncSkeleton layout="kpis" label="Loading summary" />);
    expect(screen.getByRole('status', { name: 'Loading summary' })).toBeInTheDocument();
    expect(container.querySelectorAll('.classsync-skeleton__item')).toHaveLength(3);
  });
});
