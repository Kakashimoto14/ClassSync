import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DevelopmentRoleContext } from '../auth/development-role-context';
import { routeDefinitions } from '../routes/route-config';
import { RoleRoute } from '../routes/RouteGuard';
import { roomDetailPath, roomDirectoryPath } from '../lib/room-discovery';
import type { UserRole } from '../types/ui';

beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }),
  });
});
function LoginLocation() {
  const location = useLocation();
  return <p>{location.search}</p>;
}
function open(role: UserRole | null, path: string, inventory = 'demo') {
  if (routeDefinitions.find((route) => route.path === path.split('?')[0])?.kind === 'rooms') {
    const url = new URL(path, 'http://localhost');
    url.searchParams.set('inventory', inventory);
    path = url.pathname + url.search;
  }
  return render(
    <MemoryRouter initialEntries={[path]}>
      <DevelopmentRoleContext.Provider value={{ role, startDemo: vi.fn(), signOut: vi.fn() }}>
        <Routes>
          {routeDefinitions
            .filter((item) => item.kind === 'rooms' || item.kind === 'room-detail')
            .map((definition) => (
              <Route
                key={definition.id}
                path={definition.path}
                element={<RoleRoute definition={definition} />}
              />
            ))}
          <Route path="/forbidden" element={<p>Forbidden</p>} />
          <Route path="/auth/login" element={<LoginLocation />} />
        </Routes>
      </DevelopmentRoleContext.Provider>
    </MemoryRouter>,
  );
}
const main = () => within(screen.getByRole('main'));

describe('room discovery routes and interactions', () => {
  it.each(['student', 'teacher', 'administrator'] as const)(
    'offers provisional CDM inventory to %s without implying verified resources',
    (role) => {
      open(role, roomDirectoryPath(role), 'cdm');
      expect(main().getByText('59 of 59 spaces')).toBeInTheDocument();
      expect(main().getAllByRole('article')).toHaveLength(12);
      fireEvent.click(main().getByRole('button', { name: 'Next' }));
      expect(main().getByText('Page 2 of 5')).toBeInTheDocument();
      expect(main().getByRole('heading', { name: 'Rooms & spaces' })).toHaveFocus();
      fireEvent.change(main().getByRole('searchbox', { name: 'Search rooms' }), {
        target: { value: 'VGA' },
      });
      expect(main().getByText('1 of 59 spaces')).toBeInTheDocument();
      expect(main().getByText('VGA Room · Unconfirmed')).toBeInTheDocument();
      fireEvent.click(main().getByRole('link', { name: 'View PRRC 302 details' }));
      expect(main().getByText('Condition unverified')).toBeInTheDocument();
      expect(main().getAllByText('Unverified')).toHaveLength(4);
      expect(main().getByText('No recorded assignments')).toBeInTheDocument();
      expect(main().queryByText('Resource active')).not.toBeInTheDocument();
    },
  );
  it.each(
    (['student', 'teacher', 'administrator'] as const).flatMap((role) =>
      [
        ['room-sci-218', 'SCI-218'],
        ['room-eng-204', 'ENG-204'],
        ['room-lab-04', 'LAB-04'],
        ['room-nb-405', 'Room 405'],
      ].map(([id, name]) => ({ role, id, name })),
    ),
  )('opens $name through its $role detail route', ({ role, id, name }) => {
    open(role, roomDirectoryPath(role));
    expect(main().getAllByRole('article')).toHaveLength(4);
    const link = main().getByRole('link', { name: `View ${name} details` });
    expect(link).toHaveAttribute('href', roomDetailPath(role, id));
    fireEvent.click(link);
    expect(main().getByRole('heading', { level: 1, name })).toBeInTheDocument();
    expect(main().queryByRole('button', { name: /edit|book|reserve/i })).not.toBeInTheDocument();
    fireEvent.click(main().getByRole('link', { name: 'Back to Room Directory' }));
  });
  it('filters combined attributes, preserves filtered return, and resets', () => {
    open('student', '/student/rooms');
    fireEvent.click(main().getByText('Filters', { selector: 'summary' }));
    fireEvent.change(main().getByLabelText('Minimum capacity'), { target: { value: '42' } });
    fireEvent.change(main().getByLabelText('Facility'), { target: { value: 'Projector' } });
    expect(main().getByText('1 of 4 demo rooms')).toBeInTheDocument();
    fireEvent.click(main().getByRole('link', { name: 'View SCI-218 details' }));
    expect(main().queryByText('Network Fundamentals')).not.toBeInTheDocument();
    fireEvent.click(main().getByRole('link', { name: 'Back to Room Directory' }));
    expect(main().getByLabelText('Minimum capacity')).toHaveValue(42);
    expect(main().getByText('1 of 4 demo rooms')).toBeInTheDocument();
    fireEvent.change(main().getByLabelText('Search rooms'), { target: { value: 'missing' } });
    expect(main().getByText('No matching rooms')).toBeInTheDocument();
    fireEvent.click(main().getByRole('button', { name: 'Clear filters' }));
    expect(main().getByText('4 of 4 demo rooms')).toBeInTheDocument();
  });
  it('reports invalid capacity rather than matching everything', () => {
    open('teacher', '/teacher/find-room?capacity=-1');
    expect(main().getByRole('alert')).toHaveTextContent('whole number');
    expect(main().getByLabelText('Minimum capacity')).toHaveAttribute('aria-invalid', 'true');
    expect(main().getByText('No matching rooms')).toBeInTheDocument();
  });
  it.each(['/student/find-room', '/teacher/room-availability', '/admin/room-availability'])(
    'keeps %s availability unavailable while resource filters work',
    (path) => {
      const definition = routeDefinitions.find((item) => item.path === path)!;
      open(definition.role, path);
      expect(main().getByText('Time-based availability unavailable')).toBeInTheDocument();
      for (const label of ['Date', 'Start time', 'End time'])
        expect(main().getByLabelText(label)).toBeDisabled();
      expect(
        main().queryByRole('button', { name: /search availability/i }),
      ).not.toBeInTheDocument();
      fireEvent.change(main().getByLabelText('Search rooms'), { target: { value: 'lab-04' } });
      expect(main().getByText('1 of 4 demo rooms')).toBeInTheDocument();
      expect(main().getByText('Maintenance')).toBeInTheDocument();
      fireEvent.click(main().getByRole('link', { name: 'View LAB-04 details' }));
      expect(main().getByText('No recorded assignments')).toBeInTheDocument();
      fireEvent.click(main().getByRole('link', { name: 'Back to room search' }));
      expect(main().getByLabelText('Search rooms')).toHaveValue('lab-04');
    },
  );
  it.each(['', '?id=unknown', '?id=', '?id=room-sci-218&id=room-eng-204'])(
    'does not substitute SCI-218 for invalid detail parameters %s',
    (query) => {
      open('student', '/student/rooms/detail' + query);
      expect(main().getByText(query ? 'Room not found' : 'Choose a room')).toBeInTheDocument();
      expect(main().queryByText('42 seats')).not.toBeInTheDocument();
    },
  );
  it('shows unknown resource metadata without inventing it', () => {
    open('teacher', roomDetailPath('teacher', 'room-nb-405'));
    expect(main().getByText('Condition unrecorded')).toBeInTheDocument();
    expect(main().getAllByText('Not recorded')).toHaveLength(3);
    expect(main().getByText('Human Computer Interaction')).toBeInTheDocument();
    expect(main().getByRole('link', { name: 'Back to Room Directory' })).toHaveAttribute(
      'href',
      '/teacher/find-room?inventory=demo',
    );
  });
  it('shows the actual administrator draft alongside published assignments', () => {
    open('administrator', roomDetailPath('administrator', 'room-sci-218'));
    expect(main().getByText('Network Fundamentals')).toBeInTheDocument();
    expect(main().getByText('Draft')).toBeInTheDocument();
  });
  it('rejects cross-role detail access', () => {
    open('student', roomDetailPath('administrator', 'room-sci-218'));
    expect(screen.getByText('Forbidden')).toBeInTheDocument();
  });
  it('retains the room ID when a refresh requires demo access again', () => {
    const target = roomDetailPath('student', 'room-eng-204');
    open(null, target);
    expect(screen.getByText('?returnTo=' + encodeURIComponent(target))).toBeInTheDocument();
  });
});
