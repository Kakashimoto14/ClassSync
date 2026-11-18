import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { createMemoryRouter, MemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AcademicManagementPage } from './AcademicManagementPage';
import { AcademicRecordEditor } from './AcademicRecordEditor';
import { ReadinessSummary, SchedulingSourcePage } from './AcademicGenerationPage';
import { AcademicCalendarEditor } from './AcademicCalendarEditor';
import * as api from '../lib/academic-api';
import type { AcademicSnapshot, AcademicReadiness } from '../lib/academic-api';
import type { ActivityType } from '../../../../packages/shared-types/src/scheduling';
import { suppliedAcademicProgramCatalog } from '../data/academic-program-catalog';
import { appRoutes } from '../routes/app-routes';
import { writePreviewSession } from '../auth/preview-session';

vi.mock('../lib/academic-api', () => ({
  loadCurriculumCatalog: vi.fn().mockResolvedValue({ versions: [], courses: [], program_ids: {} }),
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
  vi.mocked(api.loadCurriculumCatalog).mockResolvedValue({
    status: 'unreviewed',
    versions: [],
    courses: [],
    program_ids: {},
  });
  sessionStorage.clear();
  HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.mocked(api.listAcademicPeriods).mockResolvedValue({ periods: [period] });
  vi.mocked(api.loadAcademicPeriod).mockResolvedValue(snapshot);
  vi.mocked(api.saveAcademicRecord).mockResolvedValue(snapshot);
  vi.mocked(api.checkAcademicReadiness).mockResolvedValue(missing);
});

describe('persisted academic data management', () => {
  it('keeps period setup compact with a counted category selector and opens editors inline', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/academic?period=period-a']}>
        <AcademicManagementPage />
      </MemoryRouter>,
    );
    await screen.findByRole('heading', { name: 'Set up Entered term' });
    expect(screen.getByText('Calendar setup')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Programs 1/ })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /Subjects 1/ })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.queryByRole('heading', { name: 'Subjects', level: 3 })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Subjects 1/ }));
    expect(screen.getByRole('heading', { name: 'Subjects', level: 3 })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Programs', level: 3 })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Add subject' }));
    expect(screen.getByRole('form', { name: 'New subjects record' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save Record' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
  });

  it('uses fixed year and letter menus for degree sections', () => {
    render(
      <AcademicRecordEditor
        kind="sections"
        snapshot={snapshot}
        onSaved={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByRole('combobox', { name: 'Year level' })).toHaveValue('');
    expect(
      within(screen.getByRole('combobox', { name: 'Year level' })).getAllByRole('option'),
    ).toHaveLength(5);
    expect(screen.getByRole('combobox', { name: 'Section identifier' })).toHaveValue('');
    expect(
      within(screen.getByRole('combobox', { name: 'Section identifier' })).getAllByRole('option'),
    ).toHaveLength(27);
  });

  it('creates a period program from the supplied catalog instead of typed labels', async () => {
    render(
      <AcademicRecordEditor
        kind="programs"
        snapshot={snapshot}
        onSaved={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const program = screen.getByRole('combobox', { name: 'Program from supplied catalog' });
    expect(within(program).queryByRole('option', { name: /BSIT/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'Program acronym' })).not.toBeInTheDocument();
    fireEvent.change(program, { target: { value: 'bscpe' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Record' }));
    await waitFor(() => expect(api.saveAcademicRecord).toHaveBeenCalled());
    expect(api.saveAcademicRecord).toHaveBeenCalledWith(
      'period-a',
      expect.objectContaining({
        record: expect.objectContaining({
          kind: 'programs',
          id: 'bscpe',
          acronym: 'BSCPE',
          name: 'Computer Engineering',
        }),
      }),
    );
  });

  it('disables catalog program creation when every supplied entry is already saved', async () => {
    vi.mocked(api.loadAcademicPeriod).mockResolvedValueOnce({
      ...snapshot,
      records: [
        ...snapshot.records.filter((entry) => entry.record.kind !== 'programs'),
        ...suppliedAcademicProgramCatalog.map((record) => ({
          revision: 1,
          updated_at: period.created_at,
          updated_by: 'development-academic-sandbox',
          record: { ...record, kind: 'programs' as const, active: true },
        })),
      ],
    });
    render(
      <MemoryRouter initialEntries={['/admin/academic?period=period-a']}>
        <AcademicManagementPage />
      </MemoryRouter>,
    );
    await screen.findByRole('heading', { name: 'Set up Entered term' });
    expect(screen.getByRole('button', { name: 'All supplied programs added' })).toBeDisabled();
  });

  it('offers only activity and program compatible schedulable rooms', () => {
    const catalogSnapshot: AcademicSnapshot = {
      ...snapshot,
      records: [
        ...snapshot.records,
        {
          revision: 1,
          updated_at: period.created_at,
          updated_by: 'development-academic-sandbox',
          record: {
            kind: 'sections',
            id: 'section-a',
            period_id: period.id,
            program_id: 'bsit',
            year_level: 1,
            section_letter: 'A',
            active: true,
          },
        },
        ...(
          [
            {
              id: 'cdm-prrc-101',
              name: 'PRRC 101',
              schedulable: true,
              allowed_activity_types: ['academic_instruction'],
            },
            {
              id: 'cdm-prrc-302',
              name: 'PRRC 302',
              alias: 'COMLAB1',
              schedulable: true,
              allowed_activity_types: ['computer_lab_instruction'],
            },
            {
              id: 'cdm-prrc-108',
              name: 'PRRC 108',
              alias: 'ITE Science Lab',
              schedulable: true,
              allowed_activity_types: ['bse_science_instruction'],
              allowed_program_ids: ['bsed-sci'],
            },
            {
              id: 'cdm-prrc-204',
              name: 'PRRC 204',
              schedulable: false,
              allowed_activity_types: ['academic_instruction'],
            },
          ] as Array<{
            id: string;
            name: string;
            alias?: string;
            schedulable: boolean;
            allowed_activity_types: ActivityType[];
            allowed_program_ids?: string[];
          }>
        ).map((room) => ({
          revision: 1,
          updated_at: period.created_at,
          updated_by: 'development-academic-sandbox',
          record: {
            ...room,
            kind: 'resources' as const,
            building: 'PRRC',
            source: 'cdm-provisional' as const,
            active: true,
            condition: 'unknown' as const,
            room_type: room.id === 'cdm-prrc-302' ? 'computer_lab' : 'lecture_classroom',
            type_verified: false,
            verification_note: 'Inventory row designation only.',
          },
        })),
      ],
    };
    render(
      <AcademicRecordEditor
        kind="offerings"
        snapshot={catalogSnapshot}
        onSaved={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByRole('combobox', { name: 'Subject' }), {
      target: { value: 'subject-a' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Section' }), {
      target: { value: 'section-a' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Activity type' }), {
      target: { value: 'computer_lab_instruction' },
    });
    fireEvent.click(screen.getByText('Activity-compatible schedulable rooms · 0 selected'));
    expect(screen.getByRole('checkbox', { name: /PRRC 302/ })).toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: /PRRC 101/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: /PRRC 108/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: /PRRC 204/ })).not.toBeInTheDocument();
  });
  it('starts a missing academic calendar blank and does not invent dates or teaching days', () => {
    render(<AcademicCalendarEditor snapshot={snapshot} onSaved={vi.fn()} />);
    expect(screen.getByRole('textbox', { name: 'Academic year' })).toHaveValue('');
    expect(screen.getByLabelText('Effective start')).toHaveValue('');
    expect(screen.getByLabelText('Effective end')).toHaveValue('');
    for (const day of [
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
      'Sunday',
    ]) {
      expect(screen.getByRole('checkbox', { name: day })).not.toBeChecked();
    }
    expect(screen.getByRole('button', { name: 'Save academic calendar' })).toBeDisabled();
  });
  it('routes calendar and shared-scope blockers to the Administrator input screens', () => {
    const checked = {
      ...missing,
      issues: [
        {
          severity: 'blocking' as const,
          code: 'missing_academic_calendar',
          message: 'Enter calendar.',
        },
        { severity: 'blocking' as const, code: 'scope_not_complete', message: 'Review scope.' },
      ],
    };
    render(
      <MemoryRouter>
        <ReadinessSummary checked={checked} />
      </MemoryRouter>,
    );
    expect(screen.getByRole('link', { name: 'Review academic calendar' })).toHaveAttribute(
      'href',
      '/admin/academic?period=period-a',
    );
    expect(
      screen.getByRole('link', { name: 'Review period scope and fixed assignments' }),
    ).toHaveAttribute('href', '/admin/scheduling-constraints?period=period-a');
  });
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
    const subjectsArea = screen.getByRole('button', { name: /Subjects/ });
    expect(subjectsArea).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(subjectsArea);
    expect(subjectsArea).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('link', { name: 'View all subjects' })).toHaveAttribute(
      'href',
      '/admin/subjects?period=period-a',
    );
    expect(api.saveAcademicRecord).not.toHaveBeenCalled();
  });
  it('explains the full setup before an admin chooses a period', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/offerings']}>
        <AcademicManagementPage initialKind="offerings" />
      </MemoryRouter>,
    );
    await screen.findByRole('heading', { name: 'Choose a period to continue' });
    expect(screen.getByRole('button', { name: 'New academic period' })).toBeInTheDocument();
    for (const area of [
      'Approved dates and instructional days',
      'Supplied catalogs and confirmed cohort records',
      'Assigned subjects, windows and workload limits',
      'Confirmed classes and verified room suitability',
      'Teaching windows, shared scope and fixed commitments',
    ])
      expect(screen.getByText(area)).toBeInTheDocument();
    expect(screen.getByText(/not verified institutional records/i)).toBeInTheDocument();
  });
  it('keeps the sample scenario behind a development-only tool at the bottom of setup', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/academic']}>
        <AcademicManagementPage />
      </MemoryRouter>,
    );
    await screen.findByRole('heading', { name: 'Choose a period to continue' });
    const tool = screen.getByRole('region', { name: 'Development tools' });
    expect(tool).toHaveAttribute('id', 'sample-scenario');
    expect(within(tool).getByText('Sample Academic Scenario')).toBeInTheDocument();
    expect(
      (screen
        .getByRole('heading', { name: 'Choose a period to continue' })
        .compareDocumentPosition(tool) &
        Node.DOCUMENT_POSITION_FOLLOWING) !==
        0,
    ).toBe(true);
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
    expect(
      screen.getByRole('checkbox', { name: 'Faculty availability Monday 1' }),
    ).not.toBeChecked();
    expect(screen.getByRole('combobox', { name: 'Faculty availability start 1' })).toHaveValue('');
    expect(screen.getByRole('combobox', { name: 'Faculty availability end 1' })).toHaveValue('');
    fireEvent.click(screen.getByRole('checkbox', { name: 'Faculty availability Wednesday 1' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Faculty availability Friday 1' }));
    fireEvent.change(screen.getByRole('combobox', { name: 'Faculty availability start 1' }), {
      target: { value: '540' },
    });
    expect(
      within(screen.getByRole('combobox', { name: 'Faculty availability start 1' })).getAllByRole(
        'option',
      ),
    ).toHaveLength(49);
    fireEvent.change(screen.getByRole('combobox', { name: 'Faculty availability end 1' }), {
      target: { value: '720' },
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
          availability: [
            { day: 2, start: 540, end: 720 },
            { day: 4, start: 540, end: 720 },
          ],
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
    await screen.findByText('1 blocking issue');
    expect(screen.getByRole('button', { name: 'Generate Weekly Schedule' })).toBeDisabled();
    expect(screen.getAllByText('Assign an eligible instructor.')[0]).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Resolve Requirements' }));
    expect(screen.getByRole('region', { name: 'Requirements to resolve' })).toHaveFocus();
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
