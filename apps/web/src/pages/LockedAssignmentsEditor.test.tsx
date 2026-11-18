import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AcademicSnapshot } from '../lib/academic-api';
import { LockedAssignmentsEditor } from './LockedAssignmentsEditor';

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
        kind: 'subjects',
        id: 'subject-a',
        code: 'USER-A',
        name: 'Entered subject',
        required_weekly_minutes: 180,
        patterns: [{ id: 'one-180', durations: [180] }],
      },
    },
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
    {
      revision: 1,
      updated_at: period.created_at,
      updated_by: 'development-academic-sandbox',
      record: { kind: 'faculty', id: 'faculty-a', name: 'Faculty A', active: true },
    },
    {
      revision: 1,
      updated_at: period.created_at,
      updated_by: 'development-academic-sandbox',
      record: {
        kind: 'resources',
        id: 'cdm-prrc-101',
        name: 'PRRC 101',
        building: 'PRRC',
        active: true,
      },
    },
    {
      revision: 1,
      updated_at: period.created_at,
      updated_by: 'development-academic-sandbox',
      record: {
        kind: 'offerings',
        id: 'offering-a',
        subject_id: 'subject-a',
        section_id: 'section-a',
        teacher_ids: ['faculty-a'],
        room_ids: ['cdm-prrc-101'],
        active: true,
      },
    },
  ],
};

describe('fixed assignment entry', () => {
  it('uses menus and limits end times to the selected offering pattern', () => {
    const onChange = vi.fn();
    render(<LockedAssignmentsEditor snapshot={snapshot} value={[]} onChange={onChange} />);

    fireEvent.change(screen.getByRole('combobox', { name: 'Subject offering' }), {
      target: { value: 'offering-a' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Day' }), {
      target: { value: '2' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Start time' }), {
      target: { value: '08:00' },
    });

    const end = screen.getByRole('combobox', { name: 'End time' });
    expect(end).toBeEnabled();
    expect(within(end).getAllByRole('option')).toHaveLength(2);
    expect(within(end).getByRole('option', { name: '11:00' })).toBeInTheDocument();

    fireEvent.change(end, { target: { value: '11:00' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Eligible faculty' }), {
      target: { value: 'faculty-a' },
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Eligible classroom' }), {
      target: { value: 'cdm-prrc-101' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add fixed assignment' }));

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({
        offering_id: 'offering-a',
        day: 2,
        start: 480,
        end: 660,
        room_id: 'cdm-prrc-101',
        teacher_id: 'faculty-a',
      }),
    ]);
  });
});
