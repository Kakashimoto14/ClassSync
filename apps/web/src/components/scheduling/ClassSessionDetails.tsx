import { facultyDisplayName } from '../../lib/presentation-sample';
import { sessionRoomPath } from '../../lib/session-room';
import { Link } from 'react-router-dom';
import { CalendarDays, Clock3, MapPin } from 'lucide-react';
import { DialogSurface } from '../ui/DialogSurface';
import { Button } from '../ui/Button';
import { calendarDateLabel, manilaTime, type CalendarOccurrence } from '../../lib/calendar-model';
import type { UserRole } from '../../types/ui';

export function ClassSessionDetails({
  session,
  role,
  sample,
  published,
  presentation = false,
  onClose,
}: {
  session: CalendarOccurrence;
  role: UserRole;
  sample: boolean;
  published: boolean;
  presentation?: boolean;
  onClose: () => void;
}) {
  const roomPath = sessionRoomPath(role, session.room.id);
  const duration = (Date.parse(session.ends_at) - Date.parse(session.starts_at)) / 60000;
  return (
    <DialogSurface
      title={session.subject.name}
      variant="modal"
      className="class-session-overlay"
      onClose={onClose}
    >
      <div className="class-session-body">
        <div className="class-session-meta">
          <span>{session.subject.code}</span>
          <span className="session-source">
            {sample && !presentation ? 'Sample · ' : ''}
            {presentation
              ? 'Read-only presentation'
              : published
                ? 'Published'
                : 'Unpublished review'}
          </span>
        </div>
        <section className="class-session-section" aria-label="Class time">
          <h3>
            <CalendarDays size={18} aria-hidden="true" />
            {calendarDateLabel(session.date)}
          </h3>
          <p className="class-session-time">
            <Clock3 size={20} aria-hidden="true" />
            {manilaTime(session.starts_at)}–{manilaTime(session.ends_at)}
          </p>
          <p className="muted">{duration} minutes · Asia/Manila</p>
        </section>
        <section className="class-session-section" aria-label="Classroom">
          <h3>
            <MapPin size={18} aria-hidden="true" />
            Classroom
          </h3>
          <p className="class-session-room">{session.room.name}</p>
          <p>
            {session.room.building}
            {session.room.floor ? ` · ${session.room.floor}` : ''}
          </p>
        </section>
        <dl className="class-session-facts">
          <div>
            <dt>Professor</dt>
            <dd>{facultyDisplayName(session.teacher.name)}</dd>
          </div>
          <div>
            <dt>Section</dt>
            <dd>{session.section.name}</dd>
          </div>
        </dl>
        {session.changed && (
          <p className="session-change">Schedule changed · Check the time and location above.</p>
        )}
        {sample && (
          <p className="class-session-note">
            Demonstration data.{' '}
            {session.room.id.startsWith('synthetic-')
              ? 'This sample room is not a verified CdM facility. '
              : ''}
            Room capacity and equipment are unverified.
          </p>
        )}
      </div>
      <footer className="class-session-footer">
        {roomPath && (
          <Link className="button button--secondary" to={roomPath}>
            Open Room Details
          </Link>
        )}
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      </footer>
    </DialogSurface>
  );
}
