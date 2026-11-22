import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';

const source = vi.hoisted(() => ({ timetable: vi.fn(), sandboxEnabled: false }));
vi.mock('../lib/publication-api', () => ({ timetableRequest: source.timetable }));
vi.mock('../lib/scheduling-api', () => ({
  get schedulingSandboxEnabled() {
    return source.sandboxEnabled;
  },
}));

import { PublicationAuditPage } from './PublicationAuditPage';

beforeEach(() => {
  vi.clearAllMocks();
  source.sandboxEnabled = false;
  source.timetable.mockImplementation(async (path: string) => {
    if (path === 'periods') return { periods: [{ id: 'period-1', title: 'AY 2026–2027' }] };
    if (path === 'audit/period-1')
      return {
        events: [
          {
            event_id: 'event-1',
            event_type: 'scheduling.draft.saved',
            entity_type: 'draft',
            entity_ref: 'opaque-reference',
            revision: null,
            actor_uid: 'admin-uid',
            created_at: '2026-11-17T09:00:00+08:00',
          },
          {
            event_id: 'event-2',
            event_type: 'scheduling.publication.published',
            entity_type: 'publication',
            entity_ref: 'opaque-publication',
            revision: 2,
            actor_uid: 'admin-uid',
            created_at: '2026-11-17T10:00:00+08:00',
          },
        ],
      };
    throw new Error(`Unexpected request ${path}`);
  });
});

it('loads period activity from the connected audit endpoint without exposing payloads', async () => {
  render(<PublicationAuditPage />);
  fireEvent.change(await screen.findByLabelText('Academic period'), {
    target: { value: 'period-1' },
  });
  expect(await screen.findByText('Schedule draft saved')).toBeInTheDocument();
  expect(await screen.findByText('Timetable published')).toBeInTheDocument();
  expect(source.timetable).toHaveBeenCalledWith('audit/period-1');
  expect(screen.queryByText('opaque-reference')).not.toBeInTheDocument();
  expect(screen.getByText(/metadata only, not academic record payloads/)).toBeInTheDocument();
});

it('paginates bounded preview publication history', async () => {
  source.sandboxEnabled = true;
  source.timetable.mockImplementation(async (path: string) => {
    if (path === 'sandbox/periods')
      return { periods: [{ id: 'period-1', title: 'AY 2026–2027' }] };
    if (path.endsWith('&offset=0'))
      return {
        has_more: true,
        versions: [{
          id: 'publication-new',
          revision: 2,
          actor: 'admin-uid',
          created_at: '2026-11-17T10:00:00+08:00',
        }],
      };
    if (path.endsWith('&offset=50'))
      return {
        has_more: false,
        versions: [{
          id: 'publication-old',
          revision: 1,
          actor: 'admin-uid',
          created_at: '2026-11-16T10:00:00+08:00',
        }],
      };
    throw new Error(`Unexpected request ${path}`);
  });

  render(<PublicationAuditPage />);
  fireEvent.change(await screen.findByLabelText('Academic period'), {
    target: { value: 'period-1' },
  });
  expect(await screen.findByText(/revision 2/)).toBeInTheDocument();
  expect(source.timetable).toHaveBeenCalledWith(
    'history/period-1?dataset=synthetic&limit=50&offset=0',
  );

  fireEvent.click(screen.getByRole('button', { name: 'Older history' }));
  expect(await screen.findByText(/revision 1/)).toBeInTheDocument();
  expect(source.timetable).toHaveBeenCalledWith(
    'history/period-1?dataset=synthetic&limit=50&offset=50',
  );
});
