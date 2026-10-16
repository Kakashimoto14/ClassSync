import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import {
  PreviewConflictView,
  PreviewRequestsView,
  PreviewScheduleView,
  PreviewRequestCreateView,
} from './PreviewOperationsViews';
import { TeacherDashboard } from './dashboards/TeacherDashboard';
import { AdministratorDashboard } from './dashboards/AdministratorDashboard';
import { schedulePreview } from '../data/schedule-preview';

describe('dashboard destination consistency', () => {
  it('opens the selected declined request, retains its assignment, and returns to the list', () => {
    render(
      <MemoryRouter initialEntries={['/teacher/dashboard']}>
        <Routes>
          <Route path="/teacher/dashboard" element={<TeacherDashboard data={schedulePreview} />} />
          <Route
            path="/teacher/change-requests/detail"
            element={<PreviewRequestsView role="teacher" detail />}
          />
          <Route path="/teacher/change-requests" element={<PreviewRequestsView role="teacher" />} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('link', { name: 'View request: Web Systems' }));
    expect(screen.getByText('Declined')).toBeInTheDocument();
    expect(screen.queryByText('Pending review')).not.toBeInTheDocument();
    expect(screen.getByText(/ENG-204 · Prof. Maria Santos/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('link', { name: 'Back to requests' }));
    expect(screen.getAllByRole('article')).toHaveLength(2);
  });
  it('opens the same conflict and assignments shown by the Administrator dashboard', () => {
    render(
      <MemoryRouter initialEntries={['/admin/dashboard']}>
        <Routes>
          <Route
            path="/admin/dashboard"
            element={<AdministratorDashboard data={schedulePreview} />}
          />
          <Route path="/admin/conflicts/detail" element={<PreviewConflictView detail />} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('link', { name: 'Review conflict' }));
    expect(screen.getByText('Network Fundamentals')).toBeInTheDocument();
    expect(screen.getByText('Database Management Systems')).toBeInTheDocument();
    expect(screen.getAllByText('SCI-218')).toHaveLength(2);
    expect(screen.queryByText(/SCI-108/)).not.toBeInTheDocument();
    expect(screen.getByText('11:00–12:00')).toBeInTheDocument();
  });
  it.each(['request', 'conflict'] as const)(
    'does not silently substitute another record for an unknown %s ID',
    (kind) => {
      render(
        <MemoryRouter initialEntries={['/?id=missing']}>
          {kind === 'request' ? (
            <PreviewRequestsView role="teacher" detail />
          ) : (
            <PreviewConflictView detail />
          )}
        </MemoryRouter>,
      );
      expect(
        screen.getByText(kind === 'request' ? 'Request unavailable' : 'Conflict unavailable'),
      ).toBeInTheDocument();
      expect(screen.queryByText('Database Management Systems')).not.toBeInTheDocument();
    },
  );
  it('keeps teaching dates and rooms consistent, and filters actual records', () => {
    render(
      <MemoryRouter>
        <PreviewScheduleView role="teacher" />
      </MemoryRouter>,
    );
    expect(screen.getAllByRole('article')).toHaveLength(3);
    expect(screen.queryByText('Human Computer Interaction')).not.toBeInTheDocument();
    const monday = screen.getByRole('region', { name: 'Mon 12 Oct' });
    expect(
      within(monday)
        .getAllByRole('article')
        .map((item) => item.getAttribute('data-assignment-id')),
    ).toEqual(['occ-database-mon', 'occ-web-mon']);
    fireEvent.change(screen.getByRole('combobox', { name: 'Demo date' }), {
      target: { value: '2026-10-13' },
    });
    expect(screen.getAllByRole('article')).toHaveLength(1);
    fireEvent.change(screen.getByRole('textbox', { name: 'Search assignments' }), {
      target: { value: 'not-a-class' },
    });
    expect(screen.getByText('No matching assignments')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Export Schedule' })).toBeDisabled();
  });
  it('uses owned assignments for requests without claiming room availability or sending', () => {
    render(
      <MemoryRouter>
        <PreviewRequestCreateView />
      </MemoryRouter>,
    );
    const options = within(screen.getByRole('combobox', { name: 'Assigned class' })).getAllByRole(
      'option',
    );
    expect(options).toHaveLength(4);
    expect(options.map((item) => item.getAttribute('value'))).toEqual([
      '',
      'occ-database-mon',
      'occ-web-mon',
      'occ-database-tue',
    ]);
    expect(screen.getByRole('button', { name: 'Submit request' })).toBeDisabled();
    expect(screen.queryByRole('option', { name: /Available/ })).not.toBeInTheDocument();
  });
});
