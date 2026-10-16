import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { schedulePreview, type SchedulePreviewData } from '../../data/schedule-preview';
import { routesByPath } from '../../routes/route-config';
import { TeacherDashboard } from './TeacherDashboard';
import { AdministratorDashboard } from './AdministratorDashboard';

describe('UI-02 operations dashboards', () => {
  it('does not claim all attention is cleared when only conflicts are empty', () => {
    render(
      <MemoryRouter>
        <AdministratorDashboard data={{ ...schedulePreview, conflicts: [] }} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/No open conflicts in the supplied demo records/)).toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'Pending decisions' })).getByText('1 pending'),
    ).toBeInTheDocument();
    expect(screen.queryByText(/No attention items/)).not.toBeInTheDocument();
  });
  it('supports an approved decision without counting it as pending', () => {
    const data = {
      ...schedulePreview,
      requests: [{ ...schedulePreview.requests[0], status: 'approved' as const }],
    };
    render(
      <MemoryRouter>
        <TeacherDashboard data={data} />
      </MemoryRouter>,
    );
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.getByText('0 pending')).toBeInTheDocument();
  });
  it.each(['teacher', 'administrator'] as const)(
    'links only to registered %s destinations',
    (role) => {
      render(
        <MemoryRouter>
          {role === 'teacher' ? (
            <TeacherDashboard data={schedulePreview} />
          ) : (
            <AdministratorDashboard data={schedulePreview} />
          )}
        </MemoryRouter>,
      );
      for (const link of screen.getAllByRole('link')) {
        const url = new URL(link.getAttribute('href')!, 'https://example.test');
        expect(routesByPath.get(url.pathname)?.role).toBe(role);
        expect(url.pathname).not.toContain('/dashboard');
      }
    },
  );
  it('prioritizes pending requests over more recent decisions and uses stable detail identities', () => {
    render(
      <MemoryRouter>
        <TeacherDashboard data={schedulePreview} />
      </MemoryRouter>,
    );
    const requests = within(screen.getByRole('region', { name: 'Requests and decisions' }));
    const items = requests.getAllByRole('article');
    expect(within(items[0]).getByText('Pending review')).toBeInTheDocument();
    expect(within(items[1]).getByText('Declined')).toBeInTheDocument();
    expect(within(items[1]).getByRole('link')).toHaveAttribute(
      'href',
      '/teacher/change-requests/detail?id=request-equipment',
    );
  });
  it.each(['unavailable', 'unpublished', 'empty', 'finished'] as const)(
    'preserves Teacher %s state',
    (state) => {
      const data: SchedulePreviewData | null =
        state === 'unavailable'
          ? null
          : state === 'empty'
            ? { ...schedulePreview, occurrences: [] }
            : state === 'unpublished'
              ? {
                  ...schedulePreview,
                  occurrences: schedulePreview.occurrences.map((item) => ({
                    ...item,
                    publication: 'draft',
                  })),
                }
              : schedulePreview;
      render(
        <MemoryRouter>
          <TeacherDashboard
            data={data}
            reference={state === 'finished' ? '2026-10-12T15:00' : undefined}
          />
        </MemoryRouter>,
      );
      const messages = {
        unavailable: 'Schedule unavailable',
        unpublished: 'Schedule not published',
        empty: 'No classes today in this demo.',
        finished: 'All of today’s classes have finished in this demo.',
      };
      expect(screen.getByText(messages[state])).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'View teaching schedule' })).toHaveAttribute(
        'href',
        '/teacher/schedule',
      );
    },
  );
  it('retains overlapping Teacher records without repeating them in the agenda', () => {
    const data = {
      ...schedulePreview,
      occurrences: schedulePreview.occurrences.map((item) =>
        item.id === 'occ-web-mon' ? { ...item, startsAt: '2026-10-12T10:00' } : item,
      ),
    };
    render(
      <MemoryRouter>
        <TeacherDashboard data={data} reference="2026-10-12T10:30" />
      </MemoryRouter>,
    );
    const summary = screen.getByRole('region', { name: 'Next teaching assignment' });
    expect(within(summary).getByText('Overlapping assignments')).toBeInTheDocument();
    expect(within(summary).getAllByRole('article')).toHaveLength(3);
    expect(
      screen.queryByRole('region', { name: 'Remaining teaching agenda' }),
    ).not.toBeInTheDocument();
  });
  it('derives every metric from the full dataset, independently of the selected day', () => {
    render(
      <MemoryRouter>
        <AdministratorDashboard data={schedulePreview} reference="2026-10-13T09:45" />
      </MemoryRouter>,
    );
    const summary = screen.getByRole('region', { name: 'Demo record summary' });
    expect(summary.querySelector('dl')?.textContent).toBe(
      'Published4Draft1Open conflicts1Pending requests1',
    );
    expect(within(summary).getByText('All supplied demo records')).toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'Today’s campus schedule' })).getAllByRole(
        'article',
      ),
    ).toHaveLength(1);
  });
  it('reports resource conditions without inferring time-window availability', () => {
    render(
      <MemoryRouter>
        <AdministratorDashboard data={schedulePreview} />
      </MemoryRouter>,
    );
    const resources = screen.getByRole('region', { name: 'Classroom resources' });
    expect(within(resources).getByText('3 demo directory records')).toBeInTheDocument();
    expect(resources.querySelector('dl')?.textContent).toBe('Resource active2Maintenance1');
    expect(
      within(resources).getByText(/Time-based availability is unavailable/),
    ).toBeInTheDocument();
  });
  it('distinguishes unavailable resources from an empty operational dataset', () => {
    render(
      <MemoryRouter>
        <AdministratorDashboard
          data={{
            ...schedulePreview,
            resources: undefined,
            occurrences: [],
            requests: [],
            conflicts: [],
          }}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText('Resource condition data unavailable.')).toBeInTheDocument();
    expect(screen.getByText('No campus classes in this demo day')).toBeInTheDocument();
    expect(
      screen.getByText('No pending requests in the supplied demo records.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open Room Directory' })).toBeInTheDocument();
  });
});
