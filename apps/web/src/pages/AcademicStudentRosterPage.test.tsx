import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { AcademicStudentRosterPage } from './AcademicStudentRosterPage';
import { listAcademicPeriods, loadAcademicRoster, createAcademicRosterStudent,
  updateAcademicRosterStudent, deleteAcademicRosterStudent } from '../lib/academic-api';

vi.mock('../config/runtime-config', () => ({ appMode: 'institutional' }));
vi.mock('../lib/academic-api', () => ({
  listAcademicPeriods: vi.fn(),
  loadAcademicRoster: vi.fn(),
  createAcademicRosterStudent: vi.fn(),
  updateAcademicRosterStudent: vi.fn(),
  deleteAcademicRosterStudent: vi.fn(),
}));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listAcademicPeriods).mockResolvedValue({
    periods: [{ id: 'period', title: 'AY 2026-2027 · 1st Semester', revision: 1,
      created_at: '2026-01-01T00:00:00Z', source: 'institutional' }],
  });
  vi.mocked(loadAcademicRoster).mockResolvedValue({
    items: [{ student_id: '26-00101', display_name: 'Aira Santos',
      registered_email: 'student.26.00101@student.pnm.edu.ph', enrollment_status: 'unverified',
      section_id: 'section', section_label: 'BSIT-1A', year_level: 1 }],
    total: 1, limit: 20, offset: 0, period_revision: 7,
    sections: [
      { id: 'section', year_level: 1, label: 'BSIT-1A', active: true },
      { id: 'section-2', year_level: 2, label: 'BSIT-2B', active: true },
    ],
  });
  vi.mocked(createAcademicRosterStudent).mockResolvedValue({ created: true });
  vi.mocked(updateAcademicRosterStudent).mockResolvedValue({ updated: true });
  vi.mocked(deleteAcademicRosterStudent).mockResolvedValue({ deleted: true });
});

describe('connected academic student roster', () => {
  it('loads paginated tenant roster records and applies year filters', async () => {
    render(<MemoryRouter><AcademicStudentRosterPage /></MemoryRouter>);
    expect(await screen.findByText('Aira Santos')).toBeInTheDocument();
    expect(screen.getByText('26-00101')).toBeInTheDocument();
    expect(screen.getByText('Unverified')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Year level'), { target: { value: '1' } });
    expect(loadAcademicRoster).toHaveBeenLastCalledWith('period', {
      limit: 20, offset: 0, search: '', year_level: 1,
    });
  });

  it('creates a student with the selected period section and current revision', async () => {
    render(<MemoryRouter><AcademicStudentRosterPage /></MemoryRouter>);
    expect(await screen.findByText('Aira Santos')).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: '+ Add Student' }));
    const form = screen.getByRole('form', { name: 'Add student' });
    const inputs = form.querySelectorAll('input');
    fireEvent.change(inputs[0], { target: { value: 'Aira Santos' } });
    fireEvent.change(inputs[1], { target: { value: '26-00102' } });
    fireEvent.change(inputs[2], { target: { value: 'aira.santos@student.pnm.edu.ph' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Add Student' }));
    await waitFor(() => expect(createAcademicRosterStudent).toHaveBeenCalledWith('period', {
      expected_period_revision: 7, student_id: '26-00102', full_name: 'Aira Santos',
      email: 'aira.santos@student.pnm.edu.ph', year_level: 1, section_id: 'section',
      enrollment_status: 'unverified',
    }));
    expect(await screen.findByText('Student 26-00102 added to the roster.')).toBeInTheDocument();
  });

  it('edits a student and moves the enrollment to a different year section', async () => {
    render(<MemoryRouter><AcademicStudentRosterPage /></MemoryRouter>);
    expect(await screen.findByText('Aira Santos')).toBeInTheDocument();
    fireEvent.click(await screen.findByRole('button', { name: 'Edit 26-00101' }));
    const form = screen.getByRole('form', { name: 'Edit student' });
    fireEvent.change(form.querySelectorAll('select')[0], { target: { value: '2' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Save Student' }));
    await waitFor(() => expect(updateAcademicRosterStudent).toHaveBeenCalledWith('period', '26-00101', {
      expected_period_revision: 7, student_id: '26-00101', full_name: 'Aira Santos',
      email: 'student.26.00101@student.pnm.edu.ph', year_level: 2, section_id: 'section-2',
      enrollment_status: 'unverified',
    }));
    expect(await screen.findByText('Student 26-00101 updated.')).toBeInTheDocument();
  });

  it('confirms deletion and removes the row using the current period revision', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<MemoryRouter><AcademicStudentRosterPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: 'Delete 26-00101' }));
    await waitFor(() => expect(deleteAcademicRosterStudent).toHaveBeenCalledWith('period', '26-00101', 7));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('This cannot be undone.'));
    expect(await screen.findByText('Student 26-00101 deleted from the roster.')).toBeInTheDocument();
    confirm.mockRestore();
  });

  it('marks a seeded student active with the current profile and period revision', async () => {
    render(<MemoryRouter><AcademicStudentRosterPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole('button', { name: 'Mark 26-00101 active' }));
    await waitFor(() => expect(updateAcademicRosterStudent).toHaveBeenCalledWith('period', '26-00101', {
      student_id: '26-00101', full_name: 'Aira Santos',
      email: 'student.26.00101@student.pnm.edu.ph', year_level: 1, section_id: 'section',
      enrollment_status: 'active', expected_period_revision: 7,
    }));
    expect(await screen.findByRole('status')).toHaveTextContent('26-00101 is now active');
  });

  it('requires a name and email before a student can be marked active', async () => {
    vi.mocked(loadAcademicRoster).mockResolvedValue({
      items: [{ student_id: '26-00103', display_name: 'Ben Cruz', registered_email: null,
        enrollment_status: 'unverified', section_id: 'section', section_label: 'BSIT-1A',
        year_level: 1 }],
      total: 1, limit: 20, offset: 0, period_revision: 7,
      sections: [{ id: 'section', year_level: 1, label: 'BSIT-1A', active: true }],
    });
    render(<MemoryRouter><AcademicStudentRosterPage /></MemoryRouter>);
    const button = await screen.findByRole('button', { name: 'Mark 26-00103 active' });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription('Add the student’s name and institutional email first.');
    expect(updateAcademicRosterStudent).not.toHaveBeenCalled();
  });
});
