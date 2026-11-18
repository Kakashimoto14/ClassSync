import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { listSchedulingDrafts } from '../lib/scheduling-api';
import { ConflictCenterPage } from './ConflictCenterPage';

vi.mock('../lib/scheduling-api', () => ({
  schedulingSandboxEnabled: true,
  listSchedulingDrafts: vi.fn(),
  loadSchedulingDraft: vi.fn(),
}));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listSchedulingDrafts).mockResolvedValue({
    drafts: [],
    has_more: false,
    limit: 25,
    offset: 0,
  });
});

it('explains the empty state and routes admins to generation or setup', async () => {
  render(
    <MemoryRouter>
      <ConflictCenterPage />
    </MemoryRouter>,
  );

  expect(
    await screen.findByRole('heading', { name: 'Generate a draft first' }),
  ).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Open schedule generation' })).toHaveAttribute(
    'href',
    '/admin/ai-scheduling',
  );
  expect(screen.getByRole('link', { name: 'Review academic setup' })).toHaveAttribute(
    'href',
    '/admin/academic',
  );
  expect(screen.getByText(/language-model explanations are not enabled/i)).toBeInTheDocument();
  expect(screen.queryByText('Planned AI assistance')).not.toBeInTheDocument();
});
