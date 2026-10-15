import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { schedulePreview } from '../../data/schedule-preview';
import { StudentDashboard } from './StudentDashboard';
import { TeacherDashboard } from './TeacherDashboard';
import { AdministratorDashboard } from './AdministratorDashboard';

describe('role-specific dashboard compositions', () => {
  it('keeps Student next class and remaining agenda in agreement without admin data', () => {
    render(
      <MemoryRouter>
        <StudentDashboard data={schedulePreview} />
      </MemoryRouter>,
    );
    const next = screen.getByRole('region', { name: 'Next class' });
    const agenda = screen.getByRole('region', { name: 'Today’s remaining classes' });
    expect(within(next).getByText('Database Management Systems')).toBeInTheDocument();
    expect(within(agenda).getByText('Database Management Systems')).toBeInTheDocument();
    expect(within(agenda).getByText('2 classes')).toBeInTheDocument();
    expect(screen.queryByText('Network Fundamentals')).not.toBeInTheDocument();
    expect(screen.queryByText('Suggested classroom')).not.toBeInTheDocument();
    for (const link of screen.getAllByRole('link'))
      expect(link.getAttribute('href')).toMatch(/^\/student\//);
  });
  it('limits Teacher schedule, pending counts and links to that role', () => {
    render(
      <MemoryRouter>
        <TeacherDashboard data={schedulePreview} />
      </MemoryRouter>,
    );
    const agenda = screen.getByRole('region', { name: 'Today’s teaching agenda' });
    expect(within(agenda).getAllByText(/Prof. Maria Santos/)).toHaveLength(2);
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
    expect(screen.getByText('2 items')).toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'Needs attention' })).getAllByRole('listitem'),
    ).toHaveLength(2);
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
