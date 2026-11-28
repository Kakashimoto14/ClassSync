import './entrance-showcase.css';

const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];

// Illustration only: deliberately separate from academic records and solver state.
const sessions = [
  { day: 1, row: 1, span: 2, type: 'lecture', title: 'Lecture', room: 'Room A' },
  { day: 3, row: 1, span: 2, type: 'lecture', title: 'Lecture', room: 'Room A' },
  { day: 2, row: 2, span: 3, type: 'computer-lab', title: 'Computer lab', room: 'Lab 1' },
  { day: 4, row: 3, span: 3, type: 'science-lab', title: 'Science lab', room: 'Lab 2' },
  { day: 1, row: 4, span: 2, type: 'athletic', title: 'PE', room: 'Court' },
  { day: 5, row: 2, span: 2, type: 'lecture', title: 'Lecture', room: 'Room B' },
] as const;

const times = ['07:30', '08:30', '09:30', '10:30', '11:30'];

export function EntranceShowcase() {
  return (
    <aside className="entrance-showcase" aria-label="ClassSync campus services">
      <p className="entrance-showcase__school">Colegio de Montalban</p>
      <h2>Your classes, rooms and schedule changes in one place.</h2>
      <p className="entrance-showcase__lead">
        ClassSync is the college&rsquo;s timetable service for students, teachers and administrators.
      </p>
      <figure className="entrance-week">
        <div className="entrance-week__grid" aria-hidden="true">
          {days.map((day, index) => (
            <span className="entrance-week__day" key={day} style={{ gridColumn: index + 2 }}>
              {day}
            </span>
          ))}
          {times.map((time, index) => (
            <span className="entrance-week__time numeric" key={time} style={{ gridRow: index + 2 }}>
              {time}
            </span>
          ))}
          {sessions.map((session) => (
            <span
              className={`entrance-week__session entrance-week__session--${session.type}`}
              key={`${session.day}-${session.row}`}
              style={{
                gridColumn: session.day + 1,
                gridRow: `${session.row + 1} / span ${session.span}`,
              }}
            >
              <strong>{session.title}</strong>
              <small>{session.room}</small>
            </span>
          ))}
        </div>
        <figcaption>Illustrative week, not a live schedule.</figcaption>
      </figure>
    </aside>
  );
}
