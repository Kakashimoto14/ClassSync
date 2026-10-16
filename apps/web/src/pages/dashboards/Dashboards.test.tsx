import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { schedulePreview } from '../../data/schedule-preview';
import { StudentDashboard } from './StudentDashboard';
import { TeacherDashboard } from './TeacherDashboard';
import { AdministratorDashboard } from './AdministratorDashboard';

describe('role-specific dashboard compositions', () => {
  it('shows the next Student class once and keeps the later agenda role-owned', () => {
    render(
      <MemoryRouter>
        <StudentDashboard data={schedulePreview} />
      </MemoryRouter>,
    );
    const next = screen.getByRole('region', { name: 'Next class' });
    const agenda = screen.getByRole('region', { name: 'Later today' });
    expect(within(next).getByText('Database Management Systems')).toBeInTheDocument();
    expect(screen.getAllByText('Database Management Systems')).toHaveLength(1);
    expect(within(agenda).getByText('Web Systems')).toBeInTheDocument();
    expect(within(agenda).getByText('1 class')).toBeInTheDocument();
    expect(screen.queryByText('Network Fundamentals')).not.toBeInTheDocument();
    expect(screen.queryByText('Suggested classroom')).not.toBeInTheDocument();
    for (const link of screen.getAllByRole('link'))
      expect(link.getAttribute('href')).toMatch(/^\/student\//);
  });
  it('opens the Student schedule from the summary action', () => {
    render(
      <MemoryRouter initialEntries={['/student/dashboard']}>
        <Routes>
          <Route path="/student/dashboard" element={<StudentDashboard data={schedulePreview} />} />
          <Route path="/student/schedule" element={<h1>Student schedule destination</h1>} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('link', { name: 'View my schedule' }));
    expect(
      screen.getByRole('heading', { name: 'Student schedule destination' }),
    ).toBeInTheDocument();
  });
  it('does not repeat in-progress or next assignments below the summary', () => {
    render(
      <MemoryRouter>
        <StudentDashboard data={schedulePreview} reference="2026-10-12T10:30" />
      </MemoryRouter>,
    );
    expect(screen.getAllByText('Database Management Systems')).toHaveLength(1);
    const next = screen.getByRole('region', { name: 'Next class' });
    expect(within(next).getAllByRole('article')).toHaveLength(2);
    expect(screen.queryByRole('region', { name: 'Later today' })).not.toBeInTheDocument();
  });
  it('retains the other simultaneous assignment instead of hiding an overlap', () => {
    const data = {
      ...schedulePreview,
      occurrences: schedulePreview.occurrences.map((item) =>
        item.id === 'occ-web-mon' ? { ...item, startsAt: '2026-10-12T10:00' } : item,
      ),
    };
    render(
      <MemoryRouter>
        <StudentDashboard data={data} />
      </MemoryRouter>,
    );
    expect(screen.getByText('Multiple classes start together')).toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'Later today' })).getByText('Web Systems'),
    ).toBeInTheDocument();
  });
  it.each(['unavailable', 'unpublished', 'empty', 'finished'] as const)(
    'preserves the Student %s state and schedule escape path',
    (state) => {
      const data =
        state === 'unavailable'
          ? null
          : state === 'empty'
            ? {
                ...schedulePreview,
                students: schedulePreview.students.map((student) => ({
                  ...student,
                  assignmentIds: [],
                })),
              }
            : state === 'unpublished'
              ? {
                  ...schedulePreview,
                  occurrences: schedulePreview.occurrences.map((item) => ({
                    ...item,
                    publication: 'draft' as const,
                  })),
                }
              : schedulePreview;
      render(
        <MemoryRouter>
          <StudentDashboard
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
      expect(screen.queryByRole('region', { name: 'Later today' })).not.toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'View my schedule' })).toHaveAttribute(
        'href',
        '/student/schedule',
      );
    },
  );
  it('limits Teacher schedule, pending counts and links to that role', () => {
    render(
      <MemoryRouter>
        <TeacherDashboard data={schedulePreview} />
      </MemoryRouter>,
    );
    const agenda = screen.getByRole('region', { name: 'Remaining teaching agenda' });
    expect(within(agenda).getAllByText(/Prof. Maria Santos/)).toHaveLength(1);
    expect(within(agenda).queryByText('Database Management Systems')).not.toBeInTheDocument();
    expect(screen.getByText('1 pending')).toBeInTheDocument();
    expect(screen.queryByText('Human Computer Interaction')).not.toBeInTheDocument();
    for (const link of screen.getAllByRole('link'))
      expect(link.getAttribute('href')).toMatch(/^\/teacher\//);
  });
  it('keeps administrator counts consistent with displayed attention and schedule records', () => {
    render(
      <MemoryRouter>
        <AdministratorDashboard data={schedulePreview} />
      </MemoryRouter>,
    );
    expect(screen.getByText('1 item')).toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'Scheduling attention' })).getAllByRole('listitem'),
    ).toHaveLength(1);
    expect(
      within(screen.getByRole('region', { name: 'Pending decisions' })).getAllByRole('listitem'),
    ).toHaveLength(1);
    const agenda = screen.getByRole('region', { name: 'Today’s campus schedule' });
    expect(within(agenda).getAllByText('Published')).toHaveLength(3);
    expect(within(agenda).getAllByText('Draft')).toHaveLength(1);
    for (const link of screen.getAllByRole('link'))
      expect(link.getAttribute('href')).toMatch(/^\/admin\//);
  });
  it('does not interpret missing administrative data as zero conflicts', () => {
    render(
      <MemoryRouter>
        <AdministratorDashboard data={null} />
      </MemoryRouter>,
    );
    expect(screen.getByText('Operational data unavailable')).toBeInTheDocument();
    expect(screen.queryByText('0 items')).not.toBeInTheDocument();
  });
});
