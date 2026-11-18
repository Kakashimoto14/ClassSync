import { useMemo, useState } from 'react';
import type {
  AcademicFaculty,
  AcademicOffering,
  AcademicProgram,
  AcademicResource,
  AcademicSection,
  AcademicSubject,
  Assignment,
} from '../../../../packages/shared-types/src/scheduling';
import type { AcademicSnapshot } from '../lib/academic-api';
import { Button } from '../components/ui/Button';

const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const asMinutes = (value: string) => {
  const [hour, minute] = value.split(':').map(Number);
  return hour * 60 + minute;
};
const asTime = (value: number) =>
  `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
const startTimes = Array.from({ length: 48 }, (_, index) => index * 30);

export function LockedAssignmentsEditor({
  snapshot,
  value,
  onChange,
}: {
  snapshot: AcademicSnapshot;
  value: Assignment[];
  onChange: (value: Assignment[]) => void;
}) {
  const records = snapshot.records.map((envelope) => envelope.record);
  const offerings = records.filter(
    (record): record is AcademicOffering => record.kind === 'offerings' && record.active !== false,
  );
  const subjects = records.filter(
    (record): record is AcademicSubject => record.kind === 'subjects',
  );
  const sections = records.filter(
    (record): record is AcademicSection => record.kind === 'sections',
  );
  const faculty = records.filter(
    (record): record is AcademicFaculty => record.kind === 'faculty' && record.active !== false,
  );
  const rooms = records.filter(
    (record): record is AcademicResource => record.kind === 'resources' && record.active !== false,
  );
  const subjectById = useMemo(() => new Map(subjects.map((item) => [item.id, item])), [subjects]);
  const sectionById = useMemo(() => new Map(sections.map((item) => [item.id, item])), [sections]);
  const programById = useMemo(() => new Map(records.filter((item): item is AcademicProgram => item.kind === 'programs').map((item) => [item.id, item.acronym])), [records]);
  const facultyById = useMemo(() => new Map(faculty.map((item) => [item.id, item])), [faculty]);
  const roomById = useMemo(() => new Map(rooms.map((item) => [item.id, item])), [rooms]);
  const [offeringId, setOfferingId] = useState('');
  const [day, setDay] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [teacherId, setTeacherId] = useState('');
  const [roomId, setRoomId] = useState('');
  const [error, setError] = useState('');
  const offering = offerings.find((item) => item.id === offeringId);
  const subject = offering ? subjectById.get(offering.subject_id) : undefined;
  const patterns = offering?.patterns_override ?? subject?.patterns ?? [];
  const teachers = offering?.teacher_ids ?? [];
  const eligibleRooms = offering?.room_ids ?? [];
  const selectedStart = start ? asMinutes(start) : null;
  const allowedEndTimes = selectedStart === null
    ? []
    : [...new Set(patterns.flatMap((pattern) => pattern.durations).map((duration) => selectedStart + duration).filter((end) => end <= 1440))].sort((a, b) => a - b);

  function add() {
    setError('');
    if (!offering || !subject || !sectionById.has(offering.section_id)) {
      setError('Select a saved subject offering first.');
      return;
    }
    if (!day || !start || !end || !teacherId || !roomId) {
      setError('Choose the day, times, eligible faculty and eligible classroom.');
      return;
    }
    const begin = asMinutes(start);
    const finish = asMinutes(end);
    if (
      begin >= finish ||
      !patterns.some((pattern) => pattern.durations.includes(finish - begin))
    ) {
      setError('This fixed session duration must match an approved offering pattern.');
      return;
    }
    if (!teachers.includes(teacherId) || !eligibleRooms.includes(roomId)) {
      setError('Choose faculty and a room already allowed by this offering.');
      return;
    }
    const assignment: Assignment = {
      id: crypto.randomUUID(),
      offering_id: offering.id ?? '',
      subject_id: offering.subject_id,
      section_id: offering.section_id,
      teacher_id: teacherId,
      room_id: roomId,
      day: Number(day),
      start: begin,
      end: finish,
    };
    onChange([...value, assignment]);
    setOfferingId('');
    setDay('');
    setStart('');
    setEnd('');
    setTeacherId('');
    setRoomId('');
  }

  function assignmentLabel(assignment: Assignment) {
    const subjectRecord = subjectById.get(assignment.subject_id);
    const section = sectionById.get(assignment.section_id);
    const teacherRecord = facultyById.get(assignment.teacher_id);
    const roomRecord = roomById.get(assignment.room_id);
    return [
      subjectRecord?.code ?? assignment.subject_id,
      section ? `${programById.get(section.program_id) ?? section.program_id}${section.year_level ?? ''}${section.section_letter ?? section.custom_label ?? ''}` : assignment.section_id,
      `${dayNames[assignment.day]} ${asTime(assignment.start)}–${asTime(assignment.end)}`,
      teacherRecord?.name ?? assignment.teacher_id,
      roomRecord ? `${roomRecord.name} · ${roomRecord.building}` : assignment.room_id,
    ].join(' · ');
  }

  return (
    <section aria-label="Fixed assignments and shared commitments">
      <h3>Fixed assignments and shared institute commitments</h3>
      <p className="muted">
        Add a fixed meeting only after its subject offering, eligible faculty and eligible room are
        saved. Include ICS, IBE and ITE commitments that share faculty or rooms in this same
        academic period; separate periods are not compared for conflicts.
      </p>
      {offerings.length === 0 ? (
        <p>No active subject offerings exist in this period yet.</p>
      ) : (
        <div className="academic-field-grid">
          <label>
            Subject offering
            <select value={offeringId} onChange={(event) => setOfferingId(event.target.value)}>
              <option value="">Choose a current-period offering</option>
              {offerings.map((item) => {
                const subjectRecord = subjectById.get(item.subject_id);
                const section = sectionById.get(item.section_id);
                return (
                  <option key={item.id} value={item.id}>
                    {subjectRecord?.code ?? item.subject_id} ·{' '}
                    {section ? `${programById.get(section.program_id) ?? section.program_id}${section.year_level ?? ''}${section.section_letter ?? section.custom_label ?? ''}` : item.section_id}
                  </option>
                );
              })}
            </select>
          </label>
          <label>
            Day
            <select value={day} onChange={(event) => setDay(event.target.value)}>
              <option value="">Choose day</option>
              {dayNames.map((name, index) => (
                <option value={index} key={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Start time
            <select value={start} onChange={(e) => { setStart(e.target.value); setEnd(''); }}>
              <option value="">Choose start time</option>
              {startTimes.map((minute) => <option key={minute} value={asTime(minute)}>{asTime(minute)}</option>)}
            </select>
          </label>
          <label>
            End time
            <select value={end} disabled={!start} onChange={(e) => setEnd(e.target.value)}>
              <option value="">Choose permitted end time</option>
              {allowedEndTimes.map((minute) => <option key={minute} value={asTime(minute)}>{asTime(minute)}</option>)}
            </select>
          </label>
          <label>
            Eligible faculty
            <select value={teacherId} onChange={(event) => setTeacherId(event.target.value)}>
              <option value="">Choose eligible faculty</option>
              {teachers.map((id) => {
                const person = facultyById.get(id);
                return person ? <option key={id} value={id}>{person.name}</option> : null;
              })}
            </select>
          </label>
          <label>
            Eligible classroom
            <select value={roomId} onChange={(event) => setRoomId(event.target.value)}>
              <option value="">Choose eligible classroom</option>
              {eligibleRooms.map((id) => {
                const room = roomById.get(id);
                return room ? <option key={id} value={id}>{room.name} · {room.building}</option> : null;
              })}
            </select>
          </label>
          {offering && (
            <p className="muted">
              Permitted fixed-session durations: {patterns.flatMap((pattern) => pattern.durations).join(', ') || 'none'} minutes.
            </p>
          )}
        </div>
      )}
      <Button type="button" variant="secondary" disabled={!offering} onClick={add}>
        Add fixed assignment
      </Button>
      {error && <p role="alert" className="academic-field-error">{error}</p>}
      {value.length > 0 && (
        <ul aria-label="Saved fixed assignments">
          {value.map((assignment) => (
            <li key={assignment.id}>
              {assignmentLabel(assignment)}{' '}
              <Button
                type="button"
                variant="ghost"
                aria-label={`Remove fixed assignment ${assignmentLabel(assignment)}`}
                onClick={() => onChange(value.filter((item) => item.id !== assignment.id))}
              >
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
