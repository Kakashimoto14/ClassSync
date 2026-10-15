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
