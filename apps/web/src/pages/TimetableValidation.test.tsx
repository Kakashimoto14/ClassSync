import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { IndependentValidation } from './TimetableValidation';
import { validateWeeklySchedule, type GenerationInput } from '../lib/scheduling-api';
import scenario from '../../../../services/scheduling/scenarios/synthetic-week.json';
vi.mock('../lib/scheduling-api', () => ({ validateWeeklySchedule: vi.fn() }));
it('sends the exact snapshot and makes confirmed conflicts actionable', async () => {
  const input = scenario as GenerationInput,
    o = input.offerings![0];
  const a = {
    id: 'generated:class:1',
    offering_id: o.id,
    section_id: o.section_id,
    subject_id: o.subject_id,
    teacher_id: input.teachers![0].id,
    room_id: input.rooms![0].id,
    day: 0,
    start: 480,
    end: 660,
  };
  vi.mocked(validateWeeklySchedule).mockResolvedValue({
    valid: false,
    hard_conflict_count: 1,
    coverage: [],
    conflicts: [
      {
        code: 'room_overlap',
        message: 'These sessions overlap in the same room.',
        assignment_ids: [a.id],
      },
    ],
  });
  render(
    <MemoryRouter>
      <IndependentValidation input={input} assignments={[a]} />
    </MemoryRouter>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Validate timetable' }));
  expect(await screen.findByRole('status')).toHaveTextContent(
    'Validation failed · 1 hard conflicts',
  );
  expect(validateWeeklySchedule).toHaveBeenCalledWith(input, [a]);
  expect(screen.getByRole('link', { name: new RegExp(o.subject_name) })).toHaveAttribute(
    'href',
    '#assignment-generated%3Aclass%3A1',
  );
  expect(screen.queryByText('Resolved')).not.toBeInTheDocument();
});
