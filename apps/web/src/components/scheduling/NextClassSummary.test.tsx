import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { previewContext, schedulePreview } from '../../data/schedule-preview';
import { summarizeDay } from '../../lib/schedule-preview';
import { NextClassSummary } from './NextClassSummary';

describe('next class presentation', () => {
  it('shows the class, full time range and assigned location together', () => {
    render(
      <NextClassSummary
        schedule={summarizeDay(schedulePreview.occurrences, previewContext.reference)}
      />,
    );
    expect(screen.getByText('Database Management Systems')).toBeInTheDocument();
    expect(screen.getByText('10:00–11:30')).toBeInTheDocument();
    expect(screen.getByText('SCI-218')).toBeInTheDocument();
    expect(screen.getByText(/Science Building/)).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'Database Management Systems' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Professor')).toBeInTheDocument();
    expect(screen.getByText('Prof. Maria Santos')).toBeInTheDocument();
    expect(screen.getByText('Section')).toBeInTheDocument();
    expect(screen.getByText('BSIT 2A')).toBeInTheDocument();
    expect(screen.getByText(/Level 2/)).toBeInTheDocument();
    // The dashboard heading already establishes today's date.
    expect(screen.queryByText('Mon 12 Oct')).not.toBeInTheDocument();
  });
  it('retains a date for the next assignment on another day', () => {
    render(
      <NextClassSummary schedule={summarizeDay(schedulePreview.occurrences, '2026-10-12T16:00')} />,
    );
    expect(screen.getByText('Tue 13 Oct')).toBeInTheDocument();
  });
  it.each(['unavailable', 'unpublished', 'no-classes', 'finished'] as const)(
    'provides an honest %s state',
    (state) => {
      const messages = {
        unavailable: 'Schedule unavailable',
        unpublished: 'Schedule not published',
        'no-classes': 'No classes today in this demo.',
        finished: 'All of today’s classes have finished in this demo.',
      };
      render(
        <NextClassSummary schedule={{ ...summarizeDay([], previewContext.reference), state }} />,
      );
      expect(screen.getByText(messages[state])).toBeInTheDocument();
      expect(screen.queryByText('SCI-218')).not.toBeInTheDocument();
    },
  );
});
