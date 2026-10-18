import { Check, CalendarDays } from 'lucide-react';

// Illustration only: deliberately separate from academic records and solver state.
export function EntranceTimetable() {
  return (
    <figure className="entrance-timetable" aria-labelledby="timetable-caption">
      <div className="entrance-timetable__heading">
        <CalendarDays size={17} aria-hidden="true" />
        <strong>A week, in balance.</strong>
        <span>Weekly view</span>
      </div>
      <div className="entrance-timetable__grid" aria-hidden="true">
        <span className="timetable-day">Time</span>
        <span className="timetable-day">Mon</span>
        <span className="timetable-day">Tue</span>
        <span className="timetable-day">Wed</span>
        <span className="timetable-time">09:00</span>
        <div className="timetable-slot">
          <span className="timetable-class">
            <strong>Computing</strong>
            <span>Room A · 09:00</span>
          </span>
        </div>
        <div className="timetable-slot" />
        <div className="timetable-slot" />
        <span className="timetable-time">10:00</span>
        <div className="timetable-slot" />
        <div className="timetable-slot">
          <span className="timetable-class timetable-class--neutral">
            <strong>Mathematics</strong>
            <span>Room B · 10:00</span>
          </span>
        </div>
        <div className="timetable-slot" />
        <span className="timetable-time">11:00</span>
        <div className="timetable-slot" />
        <div className="timetable-slot" />
        <div className="timetable-slot">
          <span className="timetable-class">
            <strong>Design</strong>
            <span>Room C · 11:00</span>
          </span>
        </div>
      </div>
      <figcaption id="timetable-caption">
        <span>Illustrative timetable · Sample data</span>
        <span className="timetable-check">
          <Check size={15} aria-hidden="true" />
          Example conflict check: clear
        </span>
      </figcaption>
      <span className="visually-hidden">
        Example classes: Computing on Monday at 09:00 in Room A; Mathematics on Tuesday at 10:00 in
        Room B; Design on Wednesday at 11:00 in Room C. This is an illustration, not a live schedule
        or validation result.
      </span>
    </figure>
  );
}
