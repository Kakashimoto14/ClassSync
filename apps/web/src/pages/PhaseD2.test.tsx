import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { CalendarOccurrence } from '../lib/calendar-model';
import type { DraftDetail, GenerationInput, GenerationResult } from '../lib/scheduling-api';
import scenario from '../../../../services/scheduling/scenarios/synthetic-week.json';

const fixture = vi.hoisted(() => ({
  workspace: {} as Record<string, unknown>,
  request: vi.fn(),
  exportSchedule: vi.fn(() => 1),
}));
vi.mock('../config/runtime-config', async () => {
  const { capabilitiesFor } = await import('../config/app-mode');
  return { appMode: 'institutional', capabilities: capabilitiesFor('institutional') };
});
vi.mock('../lib/scheduling-api', () => ({
  schedulingSandboxEnabled: false,
  loadSchedulingDraft: vi.fn(),
  listSchedulingDrafts: vi.fn(),
  saveSchedulingDraft: vi.fn(),
  requestDraftAdvice: vi.fn(),
  saveDraftRevision: vi.fn(),
}));
vi.mock('./PublicationPanel', () => ({ PublicationPanel: () => null }));
vi.mock('../lib/use-schedule-workspace', () => ({ useScheduleWorkspace: () => fixture.workspace }));
vi.mock('../lib/institutional-api', () => ({ institutionalRequest: fixture.request }));
vi.mock('../lib/calendar-ics', () => ({ exportSchedule: fixture.exportSchedule }));

import * as api from '../lib/scheduling-api';
import { schedulableRooms } from '../lib/facility-issues';
import { SavedDraftDetailPage } from './SchedulingDraftPages';
import { SchedulingTimetable } from './SchedulingTimetable';
import { ClassroomRequestsPage } from './ClassroomRequestsPage';
import { TeacherIssueReportPage } from './TeacherIssueReportPage';
import { RoleScheduleWorkspace } from './RoleScheduleWorkspace';
import { StudentHome } from './StudentHome';
import { AlertsFeed } from '../components/scheduling/AlertsFeed';

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const uuid = (digit: number) => `${String(digit).repeat(8)}-1111-4111-8111-111111111111`;

const base = scenario as GenerationInput;
const input: GenerationInput = { ...base, period_id: uuid(9) };
const [first, second] = input.offerings!;
const room = input.rooms![0];
const otherRoom = input.rooms![1];
const assignments = [first, second].map((offering, index) => ({
  id: uuid(index + 1),
  offering_id: offering.id,
  day: index,
  start: 480,
  end: 660,
  room_id: room.id,
  teacher_id: input.teachers![0].id,
  section_id: offering.section_id,
  subject_id: offering.subject_id,
}));
const result: GenerationResult = {
  run_id: uuid(7),
  period_id: input.period_id,
  input_hash: 'a'.repeat(64),
  data_version: input.data_version,
  solver_status: 'feasible',
  assignments,
  total_offerings_requested: 2,
  total_offerings_scheduled: 2,
  coverage: [],
  hard_conflict_count: 0,
  diagnostics: [],
  validation: { valid: true, hard_conflict_count: 0, conflicts: [], coverage: [] },
  metadata: { solver_version: 'test', seed: 42, time_limit_seconds: 5, wall_time_seconds: 1 },
};
const draft: DraftDetail = {
  id: uuid(8),
  title: 'Owned review draft',
  period_id: input.period_id,
  created_at: '2026-10-18T00:00:00+00:00',
  creator: 'owned-administrator',
  source: 'institutional',
  status: 'draft',
  published: false,
  schema_version: 1,
  run_id: result.run_id,
  input_hash: result.input_hash,
  data_version: input.data_version,
  solver_status: 'feasible',
  session_count: 2,
  offerings_requested: 2,
  offerings_scheduled: 2,
  required_minutes: 360,
  allocated_minutes: 360,
  hard_conflict_count: 0,
  validated: true,
  input_snapshot: input,
  generation_result: result,
  validation: result.validation!,
};

const occurrence: CalendarOccurrence = {
  id: 'class-1',
  assignment_id: 'a',
  offering_id: 'o',
  date: '2026-10-30',
  starts_at: '2026-10-30T10:00:00+08:00',
  ends_at: '2026-10-30T11:30:00+08:00',
  changed: false,
  subject: { id: 's', code: 'CS101', name: 'Software Engineering' },
  section: { id: 'x', name: 'Section A' },
  teacher: { id: 't', name: 'Synthetic instructor' },
  room: { id: schedulableRooms[0].id, name: schedulableRooms[0].name, building: 'B', floor: '2' },
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-30T09:00:00+08:00'));
  vi.mocked(api.loadSchedulingDraft).mockResolvedValue(draft);
  fixture.request.mockResolvedValue({ issues: [], announcements: [] });
  fixture.workspace = {
    context: { mode: 'published', period: 'term-1', identity: '', view: 'week' },
    data: { version: 'v1', status: 'published', sections: [], teachers: [] },
    date: '2026-10-30',
    records: [occurrence],
    periods: [],
    drafts: [],
    loading: false,
    error: '',
    errorStatus: 0,
    notice: '',
    connected: true,
    retry: vi.fn(),
    change: vi.fn(),
  };
});

const openDraft = async () => {
  render(
    <MemoryRouter initialEntries={[`/drafts/${draft.id}`]}>
      <Routes>
        <Route path="/drafts/:draftId" element={<SavedDraftDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
  await screen.findByRole('heading', { name: 'Owned review draft' });
};

describe('timetables and drafts', () => {
  it('shows no raw identifier in the draft editor, advisor or session lists', async () => {
    await openDraft();
    for (const name of ['Class assignment', 'Assignment to review']) {
      const options = within(screen.getByRole('combobox', { name })).getAllByRole('option');
      expect(options).toHaveLength(2);
      for (const option of options) expect(option.textContent).not.toMatch(UUID);
      expect(options[0]).toHaveTextContent(`${first.subject_name}`);
      expect(options[0]).toHaveTextContent(`Mon 08:00 · ${room.name}`);
    }
    // Technical references stay only in the collapsed provenance block.
    const visible = document.body.cloneNode(true) as HTMLElement;
    for (const details of visible.querySelectorAll('details')) details.remove();
    expect(visible.textContent).not.toMatch(UUID);
  });

  it('preselects the session in the editor from its timetable card', async () => {
    await openDraft();
    const editor = screen.getByRole('combobox', { name: 'Class assignment' });
    fireEvent.click(
      screen.getByRole('button', { name: new RegExp(`^Edit ${second.subject_name} ·`) }),
    );
    await waitFor(() => expect(editor).toHaveValue(assignments[1].id));
    expect(editor).toHaveFocus();
  });

  it('summarizes an advised move as before and after', async () => {
    vi.mocked(api.requestDraftAdvice).mockResolvedValue({
      available: true,
      message: 'Owned advice',
      suggestions: [
        { assignment: { ...assignments[0], room_id: otherRoom.id }, reason: `Move ${uuid(1)}` },
      ],
    } as never);
    await openDraft();
    fireEvent.click(screen.getByRole('button', { name: 'Ask AI for conflict options' }));
    expect(await screen.findByText(`${room.name} → ${otherRoom.name}`)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(`Move ${uuid(1)}`);
  });

  it('filters by institute chip and labels every session type in text', () => {
    const typed: GenerationInput = {
      ...input,
      offerings: [{ ...first, activity_type: 'computer_lab_instruction' }, second],
    };
    render(<SchedulingTimetable input={typed} result={result} />);
    const chips = within(screen.getByRole('group', { name: 'Institute' }));
    expect(chips.getAllByRole('button').map((chip) => chip.textContent)).toEqual([
      'All',
      'ICS',
      'IBE',
      'ITE',
    ]);
    expect(chips.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'true');
    const cards = [...document.querySelectorAll('.generated-session')];
    expect(cards.map((card) => card.getAttribute('data-session-type'))).toEqual([
      'computer_lab',
      'lecture',
    ]);
    expect(cards[0]).toHaveTextContent('Computer lab');
    expect(cards[1]).toHaveTextContent('Lecture');
    fireEvent.click(chips.getByRole('button', { name: 'IBE' }));
    expect(chips.getByRole('button', { name: 'IBE' })).toHaveAttribute('aria-pressed', 'true');
    expect(chips.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.queryByRole('button', { name: /^Edit / })).not.toBeInTheDocument();
  });
});

const pending = {
  id: 'request-1',
  status: 'pending',
  revision: 1,
  reason: 'Owned reason',
  decision_note: null,
  context: {
    class: {
      date: '2026-11-09',
      subject: { code: 'OWN1', name: 'Owned seminar' },
      section: { name: 'Owned section' },
      room: { name: 'NB-204' },
    },
    proposed_room: { id: 'other', name: 'NB-301' },
  },
};

it.each([
  ['clear', 'No conflicts'],
  ['decided', 'Not yet validated'],
  ['failed', 'Not yet validated'],
])('labels the approval summary honestly for a %s check', async (state, label) => {
  fixture.request.mockImplementation(async (path: string) => {
    if (!path.endsWith('/preflight')) return { requests: [pending] };
    if (state === 'failed') throw new Error('Check unavailable');
    return { state, reasons: [] };
  });
  render(
    <MemoryRouter>
      <ClassroomRequestsPage role="administrator" />
    </MemoryRouter>,
  );
  expect(await screen.findByText('NB-204 → NB-301')).toBeInTheDocument();
  await waitFor(() =>
    expect(fixture.request).toHaveBeenCalledWith(
      'timetables/requests/request-1/preflight',
      expect.anything(),
    ),
  );
  expect(await screen.findByText(label)).toBeInTheDocument();
  if (state !== 'clear') expect(screen.queryByText('No conflicts')).not.toBeInTheDocument();
  if (state === 'failed')
    expect(screen.getByRole('alert')).toHaveTextContent("Couldn't check conflicts");
});

describe('teacher and student shortcuts', () => {
  it('offers room change and issue actions on the next class card', () => {
    render(
      <MemoryRouter>
        <RoleScheduleWorkspace role="teacher" dashboard />
      </MemoryRouter>,
    );
    const card = within(screen.getByRole('article', { name: 'Next teaching assignment' }));
    expect(card.getByRole('link', { name: 'Request room change' })).toHaveAttribute(
      'href',
      '/teacher/change-requests/new?period=term-1&date=2026-10-30&occurrence=class-1',
    );
    expect(card.getByRole('link', { name: 'Report room issue' })).toHaveAttribute(
      'href',
      '/teacher/report-issue?period=term-1&date=2026-10-30&occurrence=class-1',
    );
  });

  it('prefills the class and room of an issue report from ?occurrence=', async () => {
    render(
      <MemoryRouter initialEntries={['/teacher/report-issue?occurrence=class-1']}>
        <TeacherIssueReportPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByLabelText('Related class (optional)')).toHaveValue('class-1'),
    );
    expect(screen.getByLabelText('Room')).toHaveValue(schedulableRooms[0].id);
  });

  it('exports Today or Week from Student Home and links straight to the room', async () => {
    render(
      <MemoryRouter>
        <StudentHome />
      </MemoryRouter>,
    );
    expect(screen.getByRole('link', { name: 'Find room' })).toHaveAttribute(
      'href',
      `/student/rooms/detail?id=${schedulableRooms[0].id}&date=2026-10-30&schedule=1`,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Export .ics (day)' }));
    await waitFor(() =>
      expect(fixture.exportSchedule).toHaveBeenLastCalledWith(
        [occurrence],
        'student',
        'day',
        '2026-10-30',
      ),
    );
    expect(screen.getByRole('button', { name: 'Today' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Week' }));
    expect(screen.queryByRole('heading', { name: "Today's classes" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Export .ics (week)' }));
    await waitFor(() =>
      expect(fixture.exportSchedule).toHaveBeenLastCalledWith(
        [occurrence],
        'student',
        'week',
        '2026-10-30',
      ),
    );
  });

  it('marks class changes as urgent and announcements as general, in text', async () => {
    fixture.request.mockResolvedValue({
      announcements: [
        {
          id: 'n',
          title: 'Owned notice',
          body: 'Owned body',
          audience: ['student'],
          updated_at: '2026-11-01T00:00:00Z',
        },
      ],
    });
    render(
      <AlertsFeed
        role="student"
        scheduleReady
        changes={[{ ...occurrence, changed: true }]}
        action={() => null}
      />,
    );
    const notice = (await screen.findByText('Owned notice')).closest('article')!;
    expect(notice).toHaveClass('alert-entry--notice');
    expect(notice).toHaveTextContent('Announcement');
    expect(notice).not.toHaveTextContent('Urgent');
    const change = screen.getByText('Software Engineering').closest('article')!;
    expect(change).toHaveClass('alert-entry--urgent');
    expect(change).toHaveTextContent('Urgent · Class change');
  });
});
