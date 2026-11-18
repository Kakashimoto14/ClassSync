import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';

const source = vi.hoisted(() => ({ timetable: vi.fn() }));
vi.mock('../lib/publication-api', () => ({ timetableRequest: source.timetable }));
vi.mock('../lib/scheduling-api', () => ({ schedulingSandboxEnabled: false }));

import { PublicationAuditPage } from './PublicationAuditPage';

beforeEach(() => {
  vi.clearAllMocks();
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
