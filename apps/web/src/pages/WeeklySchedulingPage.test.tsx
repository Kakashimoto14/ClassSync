import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { WeeklySchedulingPage } from './WeeklySchedulingPage';
import { sectionLabel } from '../lib/scheduling-labels';
import * as api from '../lib/scheduling-api';
import type { GenerationInput, GenerationResult } from '../lib/scheduling-api';
import scenario from '../../../../services/scheduling/scenarios/synthetic-week.json';

vi.mock('../lib/scheduling-api', () => ({
  schedulingSandboxEnabled: true,
  loadSchedulingScenario: vi.fn(),
  generateWeeklySchedule: vi.fn(),
  validateWeeklySchedule: vi.fn(),
  checkSchedulingInputs: vi.fn(),
}));
const inputs = scenario as GenerationInput;
const emptyResult: GenerationResult = {
  run_id: 'run-test',
  period_id: inputs.period_id,
  input_hash: 'hash-test',
  data_version: inputs.data_version,
  solver_status: 'infeasible',
  assignments: [],
  total_offerings_requested: 12,
  total_offerings_scheduled: 0,
  coverage: [],
  hard_conflict_count: null,
  diagnostics: [{ code: 'infeasible', message: 'No legal complete schedule.' }],
  validation: null,
  metadata: { solver_version: 'test', seed: 42, wall_time_seconds: 1, time_limit_seconds: 5 },
};

beforeEach(() => {
  vi.clearAllMocks();
  HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.mocked(api.loadSchedulingScenario).mockResolvedValue(inputs);
});
function open() {
  return render(
    <MemoryRouter>
      <WeeklySchedulingPage />
    </MemoryRouter>,
  );
}
async function load() {
  fireEvent.click(screen.getByRole('button', { name: 'Load scheduling inputs' }));
  await screen.findByText('2. Review scheduling inputs');
}

describe('real scheduling workspace', () => {
  it('reviews a complete batch and prevents duplicate generation while the request is pending', async () => {
    let complete!: (r: GenerationResult) => void;
    vi.mocked(api.generateWeeklySchedule).mockReturnValue(
      new Promise((resolve) => {
        complete = resolve;
      }),
    );
    open();
    expect(screen.getByRole('button', { name: 'Generate Weekly Schedule' })).toBeDisabled();
    await load();
    expect(screen.getByText('2160 minutes')).toBeInTheDocument();
    const generate = screen.getByRole('button', { name: 'Generate Weekly Schedule' });
    fireEvent.click(generate);
    fireEvent.click(generate);
    expect(api.generateWeeklySchedule).toHaveBeenCalledTimes(1);
    expect(api.generateWeeklySchedule).toHaveBeenCalledWith(inputs);
    expect(screen.getAllByRole('button', { name: 'Working…' })[0]).toBeDisabled();
    await act(async () => complete(emptyResult));
    expect(await screen.findByText('Unschedulable — proven infeasible')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '4. Review generated result' })).toHaveFocus();
    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalledWith({
      block: 'start', behavior: 'instant',
    });
    expect(screen.getByText('No legal complete schedule.')).toBeInTheDocument();
    expect(
      screen.queryByRole('region', { name: 'Independent validation' }),
    ).not.toBeInTheDocument();
  });
  it('does not simulate success when the backend is unavailable', async () => {
    vi.mocked(api.generateWeeklySchedule).mockRejectedValue(
      new Error('Scheduling service unavailable'),
    );
    open();
    await load();
    fireEvent.click(screen.getByRole('button', { name: 'Generate Weekly Schedule' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Scheduling service unavailable');
    expect(screen.queryByText('4. Review generated result')).not.toBeInTheDocument();
  });
  it('requires input edits to be applied and validated before running them', async () => {
    open();
    await load();
    fireEvent.click(screen.getByText('Inspect or edit the complete input batch'));
    fireEvent.change(screen.getByRole('textbox', { name: 'Scheduling input JSON' }), {
      target: { value: '{broken' },
    });
    expect(screen.getByRole('button', { name: 'Generate Weekly Schedule' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Apply input changes' }));
    await screen.findByRole('alert');
    expect(api.generateWeeklySchedule).not.toHaveBeenCalled();
  });
  it('labels structured degree sections and custom TCP sections without parsing stable IDs', () => {
    expect(sectionLabel(inputs.sections?.[0], inputs)).toBe('BSIT-3A');
    expect(
      sectionLabel({ id: 'stable-tcp', program_id: 'tcp', custom_label: 'TCP Cohort A' }, inputs),
    ).toBe('TCP Cohort A');
  });
});
