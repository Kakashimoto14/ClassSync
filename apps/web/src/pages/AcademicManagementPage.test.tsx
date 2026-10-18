import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { createMemoryRouter, MemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AcademicManagementPage } from './AcademicManagementPage';
import { AcademicRecordEditor } from './AcademicRecordEditor';
import { SchedulingSourcePage } from './AcademicGenerationPage';
import * as api from '../lib/academic-api';
import type { AcademicSnapshot, AcademicReadiness } from '../lib/academic-api';
import { appRoutes } from '../routes/app-routes';
import { writePreviewSession } from '../auth/preview-session';

vi.mock('../lib/academic-api', () => ({
  listAcademicPeriods: vi.fn(),
  createAcademicPeriod: vi.fn(),
  loadAcademicPeriod: vi.fn(),
  saveAcademicRecord: vi.fn(),
  checkAcademicReadiness: vi.fn(),
  generateAcademicSchedule: vi.fn(),
}));
vi.mock('../lib/scheduling-api', () => ({
  schedulingSandboxEnabled: true,
  saveSchedulingDraft: vi.fn(),
  listSchedulingDrafts: vi.fn(),
  loadSchedulingDraft: vi.fn(),
  loadSchedulingScenario: vi.fn(),
  generateWeeklySchedule: vi.fn(),
  checkSchedulingInputs: vi.fn(),
  validateWeeklySchedule: vi.fn(),
}));
const period = {
  id: 'period-a',
  title: 'Entered term',
  revision: 2,
  created_at: '2026-10-18T00:00:00+00:00',
  source: 'development-entered' as const,
};
const snapshot: AcademicSnapshot = {
  period,
  records: [
    {
      revision: 1,
      updated_at: period.created_at,
      updated_by: 'development-academic-sandbox',
      record: {
        kind: 'programs',
        id: 'bsit',
        acronym: 'BSIT',
        name: 'Information Technology',
        institute: 'Institute of Computer Studies',
        section_policy: 'degree',
        active: true,
      },
    },
    {
      revision: 1,
      updated_at: period.created_at,
      updated_by: 'development-academic-sandbox',
      record: {
        kind: 'subjects',
        id: 'subject-a',
        code: 'USER-A',
        name: 'Entered subject',
        required_weekly_minutes: 180,
        patterns: [{ id: 'one', durations: [180] }],
        program_ids: ['bsit'],
      },
    },
  ],
};
const missing: AcademicReadiness = {
  period,
  ready: false,
  programs: 1,
  subjects: 1,
  sections: 0,
  faculty: 0,
  offerings: 0,
  eligible_resources: 0,
  inputs: null,
  issues: [
    { severity: 'blocking', code: 'missing_faculty', message: 'Assign an eligible instructor.' },
    { severity: 'warning', code: 'scope', message: 'Coverage is limited to entered offerings.' },
  ],
};
beforeEach(() => {
  vi.resetAllMocks();
  sessionStorage.clear();
  HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.mocked(api.listAcademicPeriods).mockResolvedValue({ periods: [period] });
  vi.mocked(api.loadAcademicPeriod).mockResolvedValue(snapshot);
  vi.mocked(api.saveAcademicRecord).mockResolvedValue(snapshot);
  vi.mocked(api.checkAcademicReadiness).mockResolvedValue(missing);
});

describe('persisted academic data management', () => {
  it('creates a period with explicit catalog inclusion and keeps the selected period in its URL', async () => {
    vi.mocked(api.listAcademicPeriods).mockResolvedValueOnce({ periods: [] });
    vi.mocked(api.createAcademicPeriod).mockResolvedValue(snapshot);
    render(
      <MemoryRouter initialEntries={['/admin/academic']}>
        <AcademicManagementPage />
      </MemoryRouter>,
    );
    await screen.findByRole('heading', { name: 'Create academic period' });
    fireEvent.change(screen.getByRole('textbox', { name: 'Academic period title' }), {
      target: { value: 'Entered term' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create Period' }));
    await screen.findByRole('button', { name: 'Validate Readiness' });
    expect(api.createAcademicPeriod).toHaveBeenCalledWith({
      title: 'Entered term',
      include_cdm_catalog: true,
    });
    expect(screen.getByRole('link', { name: 'Subjects' })).toHaveAttribute(
      'href',
      '/admin/subjects?period=period-a',
    );
    expect(api.saveAcademicRecord).not.toHaveBeenCalled();
  });
  it('submits a subject with explicit program ownership and only the selected weekly pattern', async () => {
    const onSaved = vi.fn();
    render(
      <AcademicRecordEditor
        kind="subjects"
        snapshot={snapshot}
        onSaved={onSaved}
        onCancel={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByRole('textbox', { name: 'Subject code' }), {
      target: { value: 'USER-B' },
    });
    fireEvent.change(screen.getByRole('textbox', { name: 'Subject name' }), {
      target: { value: 'Entered practice' },
    });
    fireEvent.click(screen.getByText('Associated programs · 0 selected'));
    fireEvent.click(screen.getByRole('checkbox', { name: 'BSIT · Information Technology' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'One 180-minute meeting' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save Record' }));
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(snapshot));
    expect(api.saveAcademicRecord).toHaveBeenCalledWith(
      'period-a',
      expect.objectContaining({
        expected_revision: 0,
        record: expect.objectContaining({
          kind: 'subjects',
          code: 'USER-B',
          program_ids: ['bsit'],
          required_weekly_minutes: 180,
          patterns: [{ id: 'two-90', durations: [90, 90], distinct_days: true }],
        }),
      }),
    );
  });
  it('prevents duplicate save clicks and reports persistence failure without a false success', async () => {
    let reject!: (reason: Error) => void;
    vi.mocked(api.saveAcademicRecord).mockReturnValue(
      new Promise((_, no) => {
        reject = no;
      }),
    );
    const onSaved = vi.fn(),
      onReload = vi.fn();
    render(
      <AcademicRecordEditor
        kind="programs"
        snapshot={snapshot}
        existing={snapshot.records[0]}
        onSaved={onSaved}
        onCancel={vi.fn()}
        onReload={onReload}
      />,
    );
    const save = screen.getByRole('button', { name: 'Save Record' });
    fireEvent.click(save);
    fireEvent.click(save);
    expect(api.saveAcademicRecord).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Saving academic record…' })).toBeDisabled();
    await act(async () => reject(new Error('Version changed. Reload records.')));
    expect(await screen.findByRole('alert')).toHaveTextContent('Version changed');
    expect(onSaved).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Reload saved records' }));
    expect(onReload).toHaveBeenCalledTimes(1);
  });
  it('collects faculty availability and explicit workload limits without inventing time windows', async () => {
    render(
      <AcademicRecordEditor
        kind="faculty"
        snapshot={snapshot}
        onSaved={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(
      within(screen.getByRole('group', { name: 'Faculty availability' })).getByText(
        'No windows supplied.',
      ),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByRole('textbox', { name: 'Faculty name' }), {
      target: { value: 'Entered instructor' },
    });
    fireEvent.click(screen.getByText('Eligible teaching subjects · 0 selected'));
    fireEvent.click(screen.getByRole('checkbox', { name: 'USER-A · Entered subject' }));
    fireEvent.click(screen.getByRole('button', { name: 'Add faculty availability window' }));
    fireEvent.change(screen.getByRole('combobox', { name: 'Faculty availability day 1' }), {
      target: { value: '2' },
    });
    fireEvent.change(screen.getByLabelText('Faculty availability start 1'), {
      target: { value: '09:00' },
    });
    fireEvent.click(screen.getByText('Workload and unavailable times'));
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Maximum weekly teaching minutes' }), {
      target: { value: '360' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save Record' }));
    await waitFor(() => expect(api.saveAcademicRecord).toHaveBeenCalled());
    expect(api.saveAcademicRecord).toHaveBeenCalledWith(
      'period-a',
      expect.objectContaining({
        record: expect.objectContaining({
          availability: [{ day: 2, start: 540, end: 720 }],
          subject_ids: ['subject-a'],
          max_weekly_minutes: 360,
        }),
      }),
    );
  });
  it('blocks generation for missing inputs, differentiates warnings and uses saved-period revisions', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/schedule-manager/create?period=period-a']}>
        <SchedulingSourcePage />
      </MemoryRouter>,
    );
    await screen.findByText('1 blocking issues');
    expect(screen.getByRole('button', { name: 'Generate Weekly Schedule' })).toBeDisabled();
    expect(screen.getAllByText('Assign an eligible instructor.')[0]).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: 'Resolve Requirements' }));
      expect(screen.getByRole('region', {name:'Requirements to resolve'})).toHaveFocus();
    expect(screen.getByRole('link', { name: 'Review faculty availability' })).toHaveAttribute(
      'href',
      '/admin/teachers?period=period-a',
    );
    expect(api.checkAcademicReadiness).toHaveBeenCalledWith('period-a');
    expect(api.generateAcademicSchedule).not.toHaveBeenCalled();
  });
  it('uses the stored revision for generation and exposes stale-version recovery', async () => {
    vi.mocked(api.checkAcademicReadiness).mockResolvedValue({
      ...missing,
      ready: true,
      issues: [],
      inputs: null,
    });
    vi.mocked(api.generateAcademicSchedule).mockRejectedValue(
      new Error('Academic inputs changed. Recheck readiness.'),
    );
    render(
      <MemoryRouter initialEntries={['/admin/schedule-manager/create?period=period-a']}>
        <SchedulingSourcePage />
      </MemoryRouter>,
    );
    await screen.findByText('Ready for generation');
    fireEvent.click(screen.getByRole('button', { name: 'Generate Weekly Schedule' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Recheck readiness');
    expect(api.generateAcademicSchedule).toHaveBeenCalledWith('period-a', 2);
    expect(screen.queryByRole('button', { name: 'Save Draft' })).not.toBeInTheDocument();
  });
  it('selects an existing period without setup, prevents duplicate runs and keeps unknown results unsaved', async () => {
    vi.mocked(api.checkAcademicReadiness).mockResolvedValue({
      ...missing,
      ready: true,
      issues: [],
    });
    let finish!: (value: Awaited<ReturnType<typeof api.generateAcademicSchedule>>) => void;
    vi.mocked(api.generateAcademicSchedule).mockReturnValue(
      new Promise((resolve) => {
        finish = resolve;
      }),
    );
    render(
      <MemoryRouter initialEntries={['/admin/ai-scheduling']}>
        <SchedulingSourcePage />
      </MemoryRouter>,
    );
    await screen.findByText('Ready for generation');
    expect(screen.getByRole('combobox', { name: 'Academic period' })).toHaveValue('period-a');
    const button = screen.getByRole('button', { name: 'Generate Weekly Schedule' });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(api.generateAcademicSchedule).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Generating weekly schedule…' })).toBeDisabled();
    await act(async () =>
      finish({
        run_id: 'run-a',
        period_id: 'period-a',
        data_version: 'v1',
        input_hash: 'hash',
        solver_status: 'unknown',
        assignments: [],
        total_offerings_requested: 1,
        total_offerings_scheduled: 0,
        coverage: [],
        hard_conflict_count: null,
        validation: null,
        diagnostics: [],
        metadata: { solver_version: 'test', seed: 42, time_limit_seconds: 5, wall_time_seconds: 5 },
      }),
    );
    expect(screen.getByText(/Unknown —/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save Draft' })).not.toBeInTheDocument();
  });
  it.each(['student', 'teacher'] as const)(
    'does not fetch academic data for a %s preview',
    async (role) => {
      writePreviewSession(role);
      const router = createMemoryRouter(appRoutes, { initialEntries: ['/admin/academic'] });
      render(<RouterProvider router={router} />);
      await screen.findByRole('heading', {
        name: 'This page is not available for your demo role.',
      });
      expect(api.listAcademicPeriods).not.toHaveBeenCalled();
      expect(JSON.parse(sessionStorage.getItem('classsync.preview.v1')!).role).toBe(role);
      router.dispose();
      sessionStorage.clear();
    },
  );
});
