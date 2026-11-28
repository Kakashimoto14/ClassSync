import { fireEvent, render, screen, within } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WeekGrid, type WeekEntry } from './WeekGrid';
import { Meter } from '../ui/Meter';
import { meterTone } from '../ui/meter-tone';

const entry = (id: string, day: number, start: number, over: Partial<WeekEntry> = {}): WeekEntry => ({
  id,
  day,
  start,
  end: start + 90,
  type: 'lecture',
  typeLabel: 'Lecture',
  title: `Subject ${id}`,
  section: 'BSIT-1A',
  teacher: 'Instructor',
  room: 'NB-204',
  ...over,
});
const entries = [
  entry('a', 0, 450),
  entry('b', 0, 600, { type: 'computer_lab', typeLabel: 'Computer lab' }),
  entry('c', 2, 630, { type: 'science_lab', typeLabel: 'Science lab' }),
  entry('d', 4, 480, { type: 'athletic', typeLabel: 'PE / Athletic' }),
];

const viewport = (matches: boolean) =>
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn((query: string) => ({ matches: matches && query === '(max-width: 767px)' })),
  });

afterEach(() => {
  delete (window as { matchMedia?: unknown }).matchMedia;
});

describe('week grid', () => {
  it('lays out Monday to Saturday by start hour and names every entry in full', () => {
    viewport(false);
    render(<WeekGrid label="Weekly timetable" entries={entries} />);
    const grid = screen.getByRole('grid', { name: 'Weekly timetable' });
    expect(within(grid).getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual([
      'Time',
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
    ]);
    expect(within(grid).getAllByRole('rowheader').map((cell) => cell.textContent)).toEqual([
      '07:00',
      '08:00',
      '09:00',
      '10:00',
    ]);
    expect(
      within(grid).getByRole('article', {
        name: 'Subject b, BSIT-1A, Monday 10:00–11:30, NB-204, Instructor, Computer lab',
      }),
    ).toHaveAttribute('data-session-type', 'computer_lab');
    // The accent colour always has a text label beside it.
    const legend = within(screen.getByRole('list', { name: 'Class types' }));
    expect(legend.getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Lecture',
      'Computer lab',
      'Science lab',
      'PE / Athletic',
    ]);
  });

  it('has one tab stop and moves it with the arrow, Home and End keys', () => {
    render(<WeekGrid label="Weekly timetable" entries={entries} />);
    const card = (id: string) => screen.getByRole('article', { name: new RegExp(`^Subject ${id},`) });
    const stops = () =>
      ['a', 'b', 'c', 'd'].filter((id) => card(id).getAttribute('tabindex') === '0');
    expect(stops()).toEqual(['a']);
    card('a').focus();
    const press = (key: string) => fireEvent.keyDown(document.activeElement!, { key });
    press('ArrowDown');
    expect(card('b')).toHaveFocus();
    // Empty days are skipped; the nearest start time wins.
    press('ArrowRight');
    expect(card('c')).toHaveFocus();
    press('ArrowRight');
    expect(card('d')).toHaveFocus();
    press('ArrowLeft');
    press('ArrowLeft');
    expect(card('b')).toHaveFocus();
    press('Home');
    expect(card('a')).toHaveFocus();
    press('End');
    expect(card('b')).toHaveFocus();
    expect(stops()).toEqual(['b']);
  });

  it('opens an entry with its full accessible name and keeps Edit one click away', () => {
    const onOpen = vi.fn();
    const onEdit = vi.fn();
    render(
      <WeekGrid
        label="Weekly timetable"
        entries={[
          entry('a', 0, 450, { onOpen }),
          entry('b', 1, 450, { onEdit, editLabel: 'Edit Subject b' }),
        ]}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /^Subject a, BSIT-1A, Monday 07:30/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Edit Subject b' }));
    expect(onOpen).toHaveBeenCalledOnce();
    expect(onEdit).toHaveBeenCalledOnce();
  });

  it('starts on the agenda list on phones and toggles back to the grid', () => {
    viewport(true);
    render(<WeekGrid label="Weekly timetable" entries={entries} />);
    expect(screen.getByRole('button', { name: 'Agenda list' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.queryByRole('grid')).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Monday timetable' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Week grid' }));
    expect(screen.getByRole('grid', { name: 'Weekly timetable' })).toBeInTheDocument();
  });

  it('keeps timetable grid styles in the one lazy stylesheet', () => {
    const sheet = (name: string) => readFileSync(resolve(__dirname, '../..', name), 'utf8');
    for (const name of ['calendar.css', 'weekly-scheduling.css'])
      expect(sheet(name)).not.toMatch(/calendar-week-grid|calendar-time-track|generated-session|weekly-grid/);
    expect(sheet('components/scheduling/week-grid.css')).toContain('.generated-session');
  });
});

describe('utilization meter', () => {
  it('is green below the high mark, amber from it and red above the limit', () => {
    expect([0, 69, 70, 90, 91].map((value) => meterTone(value, 70, 90))).toEqual([
      'ok',
      'ok',
      'high',
      'high',
      'over',
    ]);
    expect([84, 85, 100, 101].map((value) => meterTone(value, 85, 100))).toEqual([
      'ok',
      'high',
      'high',
      'over',
    ]);
  });

  it('states the value and its band in text and never overflows the track', () => {
    const { container } = render(<Meter label="Room A utilization" value={120} />);
    const meter = screen.getByRole('meter', { name: 'Room A utilization' });
    expect(meter).toHaveAttribute('aria-valuetext', '120%, over the limit');
    expect(meter).toHaveTextContent('120%');
    expect(meter).toHaveTextContent('Over');
    expect(container.querySelector<HTMLElement>('.meter__fill')!.style.width).toBe('100%');
  });

  it('does not invent a bar when the figure is unavailable', () => {
    render(<Meter label="Room B utilization" value={null} />);
    expect(screen.getByText('Not available')).toBeInTheDocument();
    expect(screen.queryByRole('meter')).not.toBeInTheDocument();
  });
});
