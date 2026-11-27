import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ReportsPage } from './ReportsPage';
import { BuildingsPage } from './BuildingsPage';
import { PeriodLifecycleControls } from './PeriodLifecycleControls';
import { RosterImportDialog } from './RosterImportDialog';
import { csvCell, toCsv } from '../lib/csv';
import { listAcademicPeriods } from '../lib/academic-api';
import * as operations from '../lib/admin-operations-api';
import { provisionalCdmRooms } from '../data/cdm-room-inventory';

vi.mock('../lib/academic-api', () => ({ listAcademicPeriods: vi.fn() }));
vi.mock('../lib/admin-operations-api', () => ({
  loadSchedulingReport: vi.fn(),
  listRestrictions: vi.fn(),
  preflightRestriction: vi.fn(),
  saveRestriction: vi.fn(),
  cloneAcademicPeriod: vi.fn(),
  archiveAcademicPeriod: vi.fn(),
  previewRosterImport: vi.fn(),
  commitRosterImport: vi.fn(),
}));

const period = {
  id: 'period', title: 'AY 2026-2027 · 1st Semester', revision: 4,
  created_at: '2026-01-01T00:00:00Z', source: 'institutional' as const,
};
const room = provisionalCdmRooms.find((item) => item.schedulable)!;
const excluded = provisionalCdmRooms.find(
  (item) => !item.schedulable && item.building === room.building,
)!;
const restriction = {
  id: 'r1', room_id: room.id, dataset: 'institutional' as const,
  starts_at: '2026-09-07T00:00:00+00:00', ends_at: '2026-09-07T02:00:00+00:00',
  kind: 'operational' as const, reason: 'Repairs', status: 'active' as const, revision: 2,
};

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listAcademicPeriods).mockResolvedValue({ periods: [period] });
});

describe('formula-safe CSV', () => {
  it('neutralizes formula prefixes and quotes separators without touching numbers', () => {
    expect(['=1+1', '+2', '-3', '@cmd', '\tx'].map(csvCell)).toEqual(
      ["'=1+1", "'+2", "'-3", "'@cmd", "'\tx"],
    );
    expect(csvCell(-5)).toBe('-5');
    expect(csvCell('=HYPERLINK("a","b")')).toBe(`"'=HYPERLINK(""a"",""b"")"`);
    expect(toCsv(['a', 'b'], [['x,y', null]])).toBe('a,b\r\n"x,y",\r\n');
  });
});

describe('reports', () => {
  it('states an unpublished period honestly and hides workload tables on utilization', async () => {
    vi.mocked(operations.loadSchedulingReport).mockResolvedValue({
      period: { id: 'period', title: period.title, revision: 4, archived_at: null },
      published: null, timezone: 'Asia/Manila',
      basis: { effective_start: '2026-08-01', effective_end: '2026-12-31', instructional_dates: 100 },
      rooms: [{ id: 'a', name: 'Room A', building: 'Hall', room_type: 'lecture_classroom',
        operating_minutes: 600, restricted_minutes: 0, available_minutes: 600,
        booked_minutes: 150, utilization: 25 }],
      buildings: [], room_types: [], faculty: [], programs: [], institutes: [], sections: [],
    });
    render(<MemoryRouter><ReportsPage utilization /></MemoryRouter>);
    expect(await screen.findByText(/no published timetable/)).toBeInTheDocument();
    const overall = screen.getByText('Overall room utilization').parentElement!;
    expect(within(overall).getByText('25%')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download Room utilization as CSV' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Faculty weekly load' })).not.toBeInTheDocument();
  });

  it('shows the service message when the report cannot be loaded', async () => {
    vi.mocked(operations.loadSchedulingReport).mockRejectedValue(new Error('Storage is unavailable'));
    render(<MemoryRouter><ReportsPage /></MemoryRouter>);
    expect(await screen.findByRole('alert')).toHaveTextContent('Storage is unavailable');
  });
});

describe('buildings and restrictions', () => {
  const open = () => {
    vi.mocked(operations.listRestrictions).mockResolvedValue({ restrictions: [restriction] });
    render(
      <MemoryRouter initialEntries={[`/admin/buildings/detail?building=${encodeURIComponent(room.building)}`]}>
        <BuildingsPage detail />
      </MemoryRouter>,
    );
  };

  it('separates schedulable rooms from excluded spaces and cancels with the saved revision', async () => {
    open();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.mocked(operations.saveRestriction).mockResolvedValue({ ...restriction, status: 'cancelled' });
    expect(await screen.findByText('Repairs')).toBeInTheDocument();
    expect(screen.getByText('2026-09-07 08:00 to 2026-09-07 10:00')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: `Restrict ${excluded.name}` })).not.toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Excluded spaces' })).getByText(excluded.name))
      .toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: `Cancel ${room.name} restriction` }));
    await waitFor(() => expect(operations.saveRestriction).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'r1', expected_revision: 2, status: 'cancelled' }),
    ));
  });

  it('requires a clean preflight before saving a restriction', async () => {
    open();
    vi.mocked(operations.preflightRestriction).mockResolvedValue({
      total: 1,
      sessions: [{ date: '2026-09-14', starts_at: '2026-09-14T08:00:00+08:00',
        ends_at: '2026-09-14T09:30:00+08:00', subject: { code: 'IT 101', name: 'Intro' },
        section: { name: 'BSIT 1A' }, teacher: { name: 'Instructor' } }],
    });
    fireEvent.click(await screen.findByRole('button', { name: `Restrict ${room.name}` }));
    const form = screen.getByRole('form', { name: 'Room restriction' });
    expect(within(form).getByRole('button', { name: 'Save restriction' })).toBeDisabled();
    fireEvent.change(within(form).getByLabelText('Starts (campus time)'), { target: { value: '2026-09-14T07:00' } });
    fireEvent.change(within(form).getByLabelText('Ends (campus time)'), { target: { value: '2026-09-14T12:00' } });
    fireEvent.change(within(form).getByLabelText('Reason'), { target: { value: 'Event' } });
    fireEvent.click(within(form).getByRole('button', { name: 'Check affected classes' }));
    expect(await within(form).findByText(/1 published class meetings overlap/)).toBeInTheDocument();
    expect(within(form).getByRole('button', { name: 'Save restriction' })).toBeDisabled();
    expect(operations.preflightRestriction).toHaveBeenCalledWith(expect.objectContaining({
      starts_at: '2026-09-14T07:00:00+08:00', expected_revision: 0,
    }));
    expect(operations.saveRestriction).not.toHaveBeenCalled();
  });
});

describe('period lifecycle', () => {
  it('archives only after explicit confirmation and never offers it twice', async () => {
    const onArchived = vi.fn();
    vi.mocked(operations.archiveAcademicPeriod).mockResolvedValue({} as never);
    const view = render(<PeriodLifecycleControls period={period} onCloned={vi.fn()} onArchived={onArchived} />);
    fireEvent.click(screen.getByRole('button', { name: 'Archive period' }));
    expect(screen.getByRole('dialog')).toHaveTextContent('cannot be undone');
    expect(operations.archiveAcademicPeriod).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Archive permanently' }));
    await waitFor(() => expect(onArchived).toHaveBeenCalled());
    expect(operations.archiveAcademicPeriod).toHaveBeenCalledWith('period', 4);
    view.rerender(<PeriodLifecycleControls period={{ ...period, archived_at: '2026-11-28T00:00:00Z' }} onCloned={vi.fn()} onArchived={onArchived} />);
    expect(screen.queryByRole('button', { name: 'Archive period' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Clone period' })).toBeInTheDocument();
  });

  it('clones under the entered title and selects the new period', async () => {
    const onCloned = vi.fn();
    vi.mocked(operations.cloneAcademicPeriod).mockResolvedValue({ period: { id: 'new' } } as never);
    render(<PeriodLifecycleControls period={period} onCloned={onCloned} onArchived={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Clone period' }));
    fireEvent.change(screen.getByLabelText('New period title'), { target: { value: 'Second semester' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create copy' }));
    await waitFor(() => expect(onCloned).toHaveBeenCalledWith('new'));
    expect(operations.cloneAcademicPeriod).toHaveBeenCalledWith('period', 'Second semester');
  });
});

describe('roster import', () => {
  const file = new File(['student_id,full_name,email,section\n'], 'roster.csv', { type: 'text/csv' });
  const row = { line: 2, student_id: '26-00200', full_name: 'New Student', email: 'n@example.edu',
    section_label: 'BSIT-1A', enrollment_status: 'unverified', action: 'create_new' as const,
    note: '', errors: [] as string[] };
  const counts = { create_new: 1, enroll_existing: 0 };

  it('blocks commit while any row is invalid', async () => {
    vi.mocked(operations.previewRosterImport).mockResolvedValue({
      rows: [{ ...row, errors: ['Student ID already exists in the university roster.'] }],
      total: 1, invalid: 1, rows_hash: null, period_revision: 7, ...counts,
    });
    render(<RosterImportDialog periodId="period" onClose={vi.fn()} onImported={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [file] } });
    expect(await screen.findByText(/1 of 1 rows need correction/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Import students' })).toBeDisabled();
  });

  it('labels every row as create new or enroll existing before committing', async () => {
    const continuing = { ...row, line: 3, student_id: '24-00101', action: 'enroll_existing' as const,
      enrollment_status: 'active', note: "Keeps current status active; the file's unverified is not applied." };
    vi.mocked(operations.previewRosterImport).mockResolvedValue({
      rows: [row, continuing], total: 2, invalid: 0, create_new: 1, enroll_existing: 1,
      rows_hash: 'b'.repeat(64), period_revision: 7,
    });
    render(<RosterImportDialog periodId="period" onClose={vi.fn()} onImported={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [file] } });
    expect(await screen.findByText(/1 create new, 1 enroll existing/)).toBeInTheDocument();
    const rows = within(screen.getByRole('region', { name: 'Import preview' })).getAllByRole('row');
    expect(rows[1]).toHaveTextContent('Create new');
    expect(rows[2]).toHaveTextContent('Enroll existing');
    expect(rows[2]).toHaveTextContent('Keeps current status active');
  });

  it('commits with the previewed hash and revision, and drops a stale preview', async () => {
    const onImported = vi.fn();
    vi.mocked(operations.previewRosterImport).mockResolvedValue({
      rows: [row], total: 1, invalid: 0, rows_hash: 'a'.repeat(64), period_revision: 7, ...counts,
    });
    vi.mocked(operations.commitRosterImport)
      .mockRejectedValueOnce(new Error('Academic data changed; reload the roster.'))
      .mockResolvedValue({ imported: 1, created: 1, enrolled_existing: 0 });
    render(<RosterImportDialog periodId="period" onClose={vi.fn()} onImported={onImported} />);
    const input = screen.getByLabelText('CSV file');
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(await screen.findByRole('button', { name: 'Import 1 students' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Academic data changed');
    expect(screen.getByRole('button', { name: 'Import students' })).toBeDisabled();
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(await screen.findByRole('button', { name: 'Import 1 students' }));
    await waitFor(() => expect(onImported).toHaveBeenCalledWith(1));
    expect(operations.commitRosterImport).toHaveBeenLastCalledWith('period', {
      csv: 'student_id,full_name,email,section\n', rows_hash: 'a'.repeat(64),
      expected_period_revision: 7,
    });
  });
});
