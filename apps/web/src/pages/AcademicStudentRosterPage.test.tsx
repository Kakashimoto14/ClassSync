import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { AcademicStudentRosterPage } from './AcademicStudentRosterPage';
import { listAcademicPeriods, loadAcademicRoster } from '../lib/academic-api';

vi.mock('../config/runtime-config', () => ({ appMode: 'institutional' }));
vi.mock('../lib/academic-api', () => ({
  listAcademicPeriods: vi.fn(),
  loadAcademicRoster: vi.fn(),
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
    total: 1, limit: 20, offset: 0,
    sections: [{ id: 'section', year_level: '1', label: 'BSIT-1A' }],
  });
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
});
