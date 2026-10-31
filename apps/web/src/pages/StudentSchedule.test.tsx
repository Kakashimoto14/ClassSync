import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { StudentSchedule } from './StudentSchedule';
import { timetableRequest } from '../lib/publication-api';
import sample from '../data/presentation-timetable.v1.json';
import { listCalendarSamples, loadSampleCalendar } from '../lib/sample-calendar-api';
vi.mock('../lib/sample-calendar-api', () => ({
  listCalendarSamples: vi.fn(),
  loadSampleCalendar: vi.fn(),
}));
vi.mock('../lib/publication-api', () => ({
  timetableRequest: vi.fn(),
  subscribeTimetable: () => () => {},
}));
beforeEach(() => {
  sessionStorage.clear();
  vi.mocked(listCalendarSamples).mockResolvedValue([
    { id: 'saved', title: 'Rich sample', period_id: 'p' },
    { id: 'saved-two', title: 'Another sample', period_id: 'p' },
  ]);
  vi.mocked(loadSampleCalendar).mockResolvedValue(sample.calendar);
  vi.mocked(timetableRequest).mockImplementation(async (path) =>
    path.endsWith('periods')
      ? { periods: [{ id: 'p', title: 'Synthetic example', calendar: sample.calendar.calendar }] }
      : sample.calendar,
  );
});

it('announces an unloaded month as pending instead of an empty schedule', async () => {
  let release!: (value: typeof sample.calendar) => void;
  const held = new Promise<typeof sample.calendar>((resolve) => {
    release = resolve;
  });
  vi.mocked(timetableRequest).mockImplementation(async (path) =>
    path.endsWith('periods')
      ? { periods: [{ id: 'p', title: 'Synthetic example', calendar: sample.calendar.calendar }] }
      : path.includes('end=2026-12-06')
        ? held
        : sample.calendar,
  );
  show();
  await waitFor(() => expect(document.querySelectorAll('.ux-agenda-row')).toHaveLength(3));
  fireEvent.click(screen.getByRole('button', { name: 'Next week' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Loading your schedule');
  expect(screen.queryByText('No classes on this day.')).not.toBeInTheDocument();
  expect(document.querySelector('.student-calendar-desktop')).toBeNull();
  release({ ...sample.calendar, occurrences: [] });
  expect(await screen.findByText('No classes on this day.')).toBeInTheDocument();
});

it('opens saved samples deliberately from a fresh workspace', async () => {
  show();
  await waitFor(() => expect(document.querySelectorAll('.ux-agenda-row')).toHaveLength(3));
  fireEvent.click(screen.getByText('Schedule options'));
  fireEvent.click(screen.getByText('Preview tools'));
  fireEvent.click(screen.getByRole('button', { name: 'Choose saved sample' }));
  expect(await screen.findByRole('option', { name: 'Rich sample' })).toBeInTheDocument();
  await waitFor(() => expect(document.querySelectorAll('.ux-agenda-row')).toHaveLength(3));
  fireEvent.change(screen.getByLabelText('Saved sample'), { target: { value: 'saved-two' } });
  await waitFor(() =>
    expect(loadSampleCalendar).toHaveBeenCalledWith(
      'saved-two',
      expect.any(String),
      expect.any(AbortSignal),
    ),
  );
  await waitFor(() => expect(document.querySelectorAll('.ux-agenda-row')).toHaveLength(3));
});

it('keeps a class ending at midnight at its real duration', async () => {
  const overnight = {
    ...sample.calendar.occurrences[0],
    date: '2026-10-30',
    starts_at: '2026-10-30T23:00:00+08:00',
    ends_at: '2026-10-31T00:00:00+08:00',
  };
  vi.mocked(timetableRequest).mockImplementation(async (path) =>
    path.endsWith('periods')
      ? { periods: [{ id: 'p', title: 'Synthetic example', calendar: sample.calendar.calendar }] }
      : { ...sample.calendar, occurrences: [overnight] },
  );
  show();
  await waitFor(() => expect(document.querySelectorAll('.student-calendar-event')).toHaveLength(1));
  expect(document.querySelector('.student-calendar-event')).toHaveStyle({ height: '86px' });
  expect(document.querySelector('.student-calendar-grid')).toHaveStyle({ height: '1440px' });
});
function show() {
  return render(
    <MemoryRouter initialEntries={['/student/schedule?period=p&date=2026-10-30&schedule=1']}>
      <StudentSchedule />
    </MemoryRouter>,
  );
}
it('opens the requested day with three classes, details, stable room IDs, week navigation and empty weekend', async () => {
  show();
  await waitFor(() => expect(document.querySelectorAll('.ux-agenda-row')).toHaveLength(3));
  const agenda = document.querySelector('.student-calendar-agenda') as HTMLElement;
  expect(within(agenda).getByRole('heading')).toHaveTextContent('Fri, Oct 30');
  fireEvent.click(within(agenda).getByRole('button', { name: /Advanced Database Systems/ }));
  expect(screen.getByRole('dialog')).toHaveTextContent('LAB-201');
  expect(
    within(screen.getByRole('dialog')).getByRole('link', { name: 'Open Room Details' }),
  ).toHaveAttribute(
    'href',
    '/student/rooms/detail?id=synthetic-student-room-1&date=2026-10-30&schedule=1&period=p',
  );
  fireEvent.click(screen.getByRole('button', { name: 'Close dialog' }));
  fireEvent.click(screen.getByRole('link', { name: 'Sat, Oct 31' }));
  expect(await screen.findByText('No classes on this day.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Next week' }));
  expect(screen.getByRole('link', { name: 'Sat, Nov 7' })).toHaveAttribute('aria-current', 'date');
  fireEvent.click(screen.getByRole('button', { name: 'Previous week' }));
  expect(screen.getByRole('link', { name: 'Sat, Oct 31' })).toHaveAttribute('aria-current', 'date');
});
it('does not render a calendar or empty-success state when the backend is unavailable', async () => {
  vi.mocked(timetableRequest).mockRejectedValue(
    Object.assign(new Error('Unavailable'), { status: 503 }),
  );
  show();
  expect(await screen.findByRole('alert')).toHaveTextContent('Your schedule is unavailable');
  expect(document.querySelector('.student-calendar-desktop')).toBeNull();
  expect(screen.queryByText('No classes on this day.')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Try again' })).toBeEnabled();
});

it('supports aligned month selection and month navigation across the year boundary', async () => {
  show();
  await waitFor(() => expect(document.querySelectorAll('.ux-agenda-row')).toHaveLength(3));
  fireEvent.click(screen.getByRole('button', { name: 'Month' }));
  const month = screen.getByRole('navigation', { name: 'Month dates' });
  expect(within(month).getAllByRole('button')).toHaveLength(31);
  expect(month.children[10]).toHaveAttribute('aria-label', 'Thu, Oct 1, 1 classes');
  fireEvent.click(screen.getByRole('button', { name: 'Next month' }));
  expect(
    within(await screen.findByRole('navigation', { name: 'Month dates' })).getAllByRole('button'),
  ).toHaveLength(30);
  fireEvent.click(screen.getByRole('button', { name: 'Next month' }));
  await screen.findByRole('navigation', { name: 'Month dates' });
  fireEvent.click(screen.getByRole('button', { name: 'Next month' }));
  expect(screen.getByText('January 2027')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Previous month' }));
  expect(screen.getByText('December 2026')).toBeInTheDocument();
});
