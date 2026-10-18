import { act, fireEvent, render, screen, within, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SaveDraftPanel, SavedDraftDetailPage, SavedDraftsPage } from './SchedulingDraftPages';
import { WeeklySchedulingPage } from './WeeklySchedulingPage';
import * as api from '../lib/scheduling-api';
import type { DraftDetail, GenerationInput, GenerationResult } from '../lib/scheduling-api';
import scenario from '../../../../services/scheduling/scenarios/synthetic-week.json';
import { appRoutes } from '../routes/app-routes';
import { writePreviewSession } from '../auth/preview-session';

vi.mock('../lib/scheduling-api', () => ({
  schedulingSandboxEnabled: true,
  saveSchedulingDraft: vi.fn(), listSchedulingDrafts: vi.fn(), loadSchedulingDraft: vi.fn(),
  generateWeeklySchedule: vi.fn(), loadSchedulingScenario: vi.fn(),
  validateWeeklySchedule: vi.fn(), checkSchedulingInputs: vi.fn(),
}));
const input = scenario as GenerationInput;
const offering = input.offerings![0];
const assignment = { id: 'session-1', offering_id: offering.id, day: 0, start: 480, end: 660,
  room_id: input.rooms![0].id, teacher_id: input.teachers![0].id,
  section_id: offering.section_id, subject_id: offering.subject_id };
const result: GenerationResult = {
  run_id: 'server-run', period_id: input.period_id, input_hash: 'a'.repeat(64),
  data_version: input.data_version, solver_status: 'feasible', assignments: [assignment],
  total_offerings_requested: 1, total_offerings_scheduled: 1,
  coverage: [{ offering_id: offering.id, required_minutes: 180, allocated_minutes: 180 }],
  hard_conflict_count: 0, diagnostics: [],
  validation: { valid: true, hard_conflict_count: 0, conflicts: [], coverage: [] },
  metadata: { solver_version: 'test', seed: 42, time_limit_seconds: 5, wall_time_seconds: 1 },
};
const draft: DraftDetail = {
  id: 'saved-id', title: 'Monday review', period_id: input.period_id,
  created_at: '2026-10-18T00:00:00+00:00', creator: 'development-sandbox',
  source: 'synthetic-preview', status: 'draft', published: false, schema_version: 1,
  run_id: result.run_id, input_hash: result.input_hash, data_version: input.data_version,
  solver_status: 'feasible', session_count: 1, offerings_requested: 1, offerings_scheduled: 1,
  required_minutes: 180, allocated_minutes: 180, hard_conflict_count: 0, validated: true,
  input_snapshot: input, generation_result: result, validation: result.validation!,
};
const list = { drafts: [draft], limit: 25, offset: 0, has_more: false };
beforeEach(() => {
  vi.resetAllMocks();
  HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.mocked(api.loadSchedulingScenario).mockResolvedValue(input);
  vi.mocked(api.generateWeeklySchedule).mockResolvedValue(result);
  vi.mocked(api.saveSchedulingDraft).mockResolvedValue(draft);
  vi.mocked(api.listSchedulingDrafts).mockResolvedValue(list);
  vi.mocked(api.loadSchedulingDraft).mockResolvedValue(draft);
});
function detail() {
  return render(<MemoryRouter initialEntries={['/admin/schedule-manager/drafts/saved-id']}><Routes>
    <Route path="/admin/schedule-manager/drafts/:draftId" element={<SavedDraftDetailPage/>}/>
  </Routes></MemoryRouter>);
}

describe('persistent scheduling draft workflow', () => {
  it('generates then saves a server run without submitting assignments or validation claims', async () => {
    render(<MemoryRouter><WeeklySchedulingPage/></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Load scheduling inputs' }));
    await screen.findByText('2. Review scheduling inputs');
    fireEvent.click(screen.getByRole('button', { name: 'Generate Weekly Schedule' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Save as Draft' }));
    await screen.findByRole('heading', { name: 'Draft saved' });
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Draft saved' })).toHaveFocus());
    expect(api.saveSchedulingDraft).toHaveBeenCalledWith({
      run_id: 'server-run', input_hash: 'a'.repeat(64),
      title: `${input.period_id} — review draft`, idempotency_key: expect.any(String),
    });
    expect(screen.getByRole('link', { name: 'Open saved draft' })).toHaveAttribute('href', '/admin/schedule-manager/drafts/saved-id');
  });
  it('prevents duplicate submissions and waits for confirmed persistence', async () => {
    let complete!: (value: DraftDetail) => void;
    vi.mocked(api.saveSchedulingDraft).mockReturnValue(new Promise(resolve => { complete = resolve; }));
    render(<MemoryRouter><SaveDraftPanel result={result}/></MemoryRouter>);
    const save = screen.getByRole('button', { name: 'Save as Draft' });
    fireEvent.click(save); fireEvent.click(save);
    expect(api.saveSchedulingDraft).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Saving draft…' })).toBeDisabled();
    expect(screen.queryByText('Draft saved')).not.toBeInTheDocument();
    await act(async () => complete(draft));
    expect(screen.getByText('Draft saved')).toBeInTheDocument();
  });
  it('shows storage errors and retries with the same idempotency key', async () => {
    vi.mocked(api.saveSchedulingDraft).mockRejectedValueOnce(new Error('Storage unavailable'));
    render(<MemoryRouter><SaveDraftPanel result={result}/></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Save as Draft' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Storage unavailable');
    expect(screen.queryByRole('link', { name: 'Open saved draft' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Save as Draft' }));
    await screen.findByText('Draft saved');
    expect(vi.mocked(api.saveSchedulingDraft).mock.calls[0][0].idempotency_key).toBe(vi.mocked(api.saveSchedulingDraft).mock.calls[1][0].idempotency_key);
  });
  it('lists and navigates to a saved unpublished draft', async () => {
    render(<MemoryRouter initialEntries={['/drafts']}><Routes>
      <Route path="/drafts" element={<SavedDraftsPage/>}/>
      <Route path="/admin/schedule-manager/drafts/:draftId" element={<SavedDraftDetailPage/>}/>
    </Routes></MemoryRouter>);
    expect(screen.getByRole('status')).toHaveTextContent('Loading saved drafts');
    fireEvent.click(await screen.findByRole('link', { name: 'Open Draft: Monday review' }));
    await screen.findByRole('heading', { name: 'Monday review' });
    expect(api.loadSchedulingDraft).toHaveBeenCalledWith('saved-id');
    expect(screen.getByText('Draft · Unpublished')).toBeInTheDocument();
    expect(api.generateWeeklySchedule).not.toHaveBeenCalled();
  });
  it('loads a direct link again after remount and filters persisted sessions', async () => {
    const first = detail();
    await screen.findByRole('heading', { name: 'Monday review' });
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Monday review' })).toHaveFocus());
    expect(document.querySelectorAll('.generated-session')).toHaveLength(1);
    const filters = within(screen.getByRole('combobox', { name: 'Day' }).parentElement!);
    fireEvent.change(filters.getByRole('combobox'), { target: { value: '1' } });
    expect(document.querySelectorAll('.generated-session')).toHaveLength(0);
    expect(screen.getByText(/No sessions match/)).toBeInTheDocument();
    first.unmount(); detail();
    await screen.findByRole('heading', { name: 'Monday review' });
    expect(api.loadSchedulingDraft).toHaveBeenCalledTimes(2);
    expect(document.querySelectorAll('.generated-session')).toHaveLength(1);
    expect(api.generateWeeklySchedule).not.toHaveBeenCalled();
  });
  it('handles empty list and failed detail retrieval with recovery', async () => {
    vi.mocked(api.listSchedulingDrafts).mockResolvedValue({ ...list, drafts: [] });
    const rendered = render(<MemoryRouter><SavedDraftsPage/></MemoryRouter>);
    expect(await screen.findByText(/No saved drafts yet/)).toBeInTheDocument();
    rendered.unmount();
    vi.mocked(api.loadSchedulingDraft).mockRejectedValueOnce(new Error('Draft not found'));
    detail();
    expect(await screen.findByRole('alert')).toHaveTextContent('Draft not found');
    fireEvent.click(screen.getByRole('button', { name: 'Retry loading draft' }));
    await screen.findByRole('heading', { name: 'Monday review' });
  });
  it('never offers a save action for infeasible output', async () => {
    vi.mocked(api.generateWeeklySchedule).mockResolvedValue({ ...result, solver_status: 'infeasible', assignments: [], validation: null, hard_conflict_count: null });
    render(<MemoryRouter><WeeklySchedulingPage/></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Load scheduling inputs' }));
    await screen.findByText('2. Review scheduling inputs');
    fireEvent.click(screen.getByRole('button', { name: 'Generate Weekly Schedule' }));
    await screen.findByText('Unschedulable — proven infeasible');
    expect(screen.queryByRole('button', { name: 'Save as Draft' })).not.toBeInTheDocument();
  });
  it.each(['student', 'teacher'] as const)('keeps %s out of saved Administrator drafts without fetching data', async role => {
    writePreviewSession(role);
    const router = createMemoryRouter(appRoutes, { initialEntries: ['/admin/schedule-manager/drafts/saved-id'] });
    render(<RouterProvider router={router}/>);
    await screen.findByRole('heading', { name: 'This page is not available for your demo role.' });
    expect(api.loadSchedulingDraft).not.toHaveBeenCalled();
    expect(JSON.parse(sessionStorage.getItem('classsync.preview.v1')!).role).toBe(role);
    router.dispose(); sessionStorage.clear();
  });
});
