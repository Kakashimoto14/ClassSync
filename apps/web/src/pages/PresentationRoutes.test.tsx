import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DevelopmentRoleContext } from '../auth/development-role-context';
import { routeDefinitions } from '../routes/route-config';
import { schedulePreview } from '../data/schedule-preview';
import { provisionalCdmRooms } from '../data/cdm-room-inventory';
import { ProductScreenPage } from './ProductScreenPage';
import { StudentDashboard } from './dashboards/StudentDashboard';
import { PreviewCalendarView } from './PreviewCalendarView';

beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
  });
});
function open(path: string, role: 'student' | 'administrator' = 'administrator') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <DevelopmentRoleContext.Provider value={{ role, startDemo: vi.fn(), signOut: vi.fn() }}>
        <Routes>
          <Route path="/student/dashboard" element={<StudentDashboard data={schedulePreview} />} />
          {routeDefinitions
            .filter((route) =>
              [
                'schedule',
                'calendar',
                'notifications',
                'requests',
                'buildings',
                'building-detail',
                'room-detail',
              ].includes(route.kind),
            )
            .map((definition) => (
              <Route
                key={definition.id}
                path={definition.path}
                element={<ProductScreenPage definition={definition} />}
              />
            ))}
        </Routes>
      </DevelopmentRoleContext.Provider>
    </MemoryRouter>,
  );
}

describe('presentation journey integrity', () => {
  it('filters Administrator classroom requests with selection-only status pills', () => {
    open('/admin/requests');
    expect(screen.getByRole('button', { name: /All 2/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('Pending review', { selector: '.status' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Declined 1/ }));
    expect(screen.getByText('Declined', { selector: '.status' })).toBeInTheDocument();
    expect(screen.queryByText('Pending review', { selector: '.status' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Declined 1/ })).toHaveAttribute('aria-pressed', 'true');
  });
  it('opens the structured Student calendar without legacy published fixtures', async () => {
    open('/student/dashboard', 'student');
    fireEvent.click(screen.getByRole('link', { name: 'View my schedule' }));
    expect(await screen.findByText('Schedule options')).toBeInTheDocument();
    expect(screen.getByRole('main').querySelectorAll('[data-assignment-id]')).toHaveLength(0);
    expect(screen.queryByText('Database Management Systems')).not.toBeInTheDocument();
  });
  it('keeps Student alerts consistent with the dashboard update and provides a working schedule action', () => {
    open('/student/notifications', 'student');
    expect(screen.queryByText(schedulePreview.updates[0].detail)).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Schedule updates' })).toBeInTheDocument();
    expect(screen.queryByText(/Room 304|hours ago|Unread/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('link', { name: 'View full schedule' }));
    expect(screen.getByRole('heading', { level: 1, name: 'My Schedule' })).toBeInTheDocument();
  });
  it.each([
    ['PRRC', 27],
    ['New Building', 24],
    ['Campus Grounds', 1],
    ['Montalban Sports Complex', 1],
  ])(
    'opens only %s rooms and returns through the same building',
    (building, count) => {
      open('/admin/buildings');
      expect(screen.queryByText(/rooms available today/)).not.toBeInTheDocument();
      fireEvent.click(screen.getByRole('link', { name: `View ${building} rooms` }));
      const main = within(screen.getByRole('main'));
      expect(main.getByRole('heading', { name: `${building} spaces` })).toBeInTheDocument();
      expect(main.getByText(new RegExp(`Showing ${Math.min(Number(count), 6)} of ${count} provisional spaces`))).toBeInTheDocument();
      const card = main.getAllByRole('article')[0];
      fireEvent.click(within(card).getByRole('link'));
      fireEvent.click(screen.getByRole('link', { name: 'Back to building' }));
      expect(screen.getByRole('heading', { name: `${building} spaces` })).toBeInTheDocument();
      fireEvent.click(screen.getByRole('link', { name: 'Back to buildings' }));
      expect(screen.getByRole('main').querySelectorAll('article')).toHaveLength(4);
      expect(provisionalCdmRooms).toHaveLength(53);
    },
  );
  it.each(['', '?building=missing', '?building=Science+Building&building=Computing+Building'])(
    'does not substitute a building for absent or invalid parameters %s',
    (query) => {
      open('/admin/buildings/detail' + query);
      expect(
        screen.getByText(
          query && !query.includes('&') ? 'Building not found' : 'Choose a building',
        ),
      ).toBeInTheDocument();
      expect(screen.queryByRole('link', { name: 'View SCI-218 details' })).not.toBeInTheDocument();
    },
  );
});

describe('calendar preview data and interaction', () => {
  it.each([
    ['student', 3],
    ['teacher', 2],
    ['administrator', 4],
  ] as const)('shows the %s-owned date and correct count', (role, count) => {
    render(
      <MemoryRouter>
        <PreviewCalendarView role={role} />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: 'October 2026' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: `Mon 12 Oct, ${count} recorded classes` }),
    ).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getAllByRole('article')).toHaveLength(count);
    expect(screen.queryByText('Draft') !== null).toBe(role === 'administrator');
    fireEvent.click(screen.getByRole('button', { name: 'Tue 13 Oct, 1 recorded class' }));
    expect(screen.getAllByRole('article')).toHaveLength(1);
    expect(screen.getByText('Database Management Systems')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Next month' }));
    expect(screen.getByRole('heading', { name: 'November 2026' })).toBeInTheDocument();
    expect(screen.getByText('No recorded classes on this date')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Previous month' }));
    expect(screen.getByRole('heading', { name: 'October 2026' })).toBeInTheDocument();
  });
});
