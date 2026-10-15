import type { UserRole } from '../types/ui';

export interface AcademicReference {
  id: string;
  name: string;
}
export interface PreviewRoom extends AcademicReference {
  building: string;
  floor?: string;
}
export interface ScheduleOccurrence {
  id: string;
  subject: AcademicReference;
  section: AcademicReference;
  teacher: AcademicReference;
  room: PreviewRoom;
  // ISO local date/time in a fictional, timezone-free scenario; never a real instant.
  startsAt: string;
  endsAt: string;
  publication: 'published' | 'draft' | 'cancelled';
}
export interface PreviewStudent extends AcademicReference {
  assignmentIds: readonly string[];
}
export type ScheduleViewer =
  { role: 'student' | 'teacher'; id: string } | { role: 'administrator' };
export interface PreviewRequest {
  id: string;
  assignmentId: string;
  teacherId: string;
  status: 'pending' | 'declined';
  updatedAt: string;
  reason: string;
}
export interface PreviewConflict {
  id: string;
  assignmentIds: readonly [string, string];
  status: 'open' | 'resolved';
  reason: string;
}
export interface PreviewUpdate {
  id: string;
  assignmentId: string;
  title: string;
  detail: string;
}
export interface SchedulePreviewData {
  occurrences: readonly ScheduleOccurrence[];
  students: readonly PreviewStudent[];
  requests: readonly PreviewRequest[];
  conflicts: readonly PreviewConflict[];
  updates: readonly PreviewUpdate[];
}

export const previewContext = {
  reference: '2026-10-12T09:45',
  label: 'Mon, 12 Oct 2026 · 09:45',
  period: 'Sample teaching week',
} as const;

export const previewProfiles: Record<
  UserRole,
  { id: string; name: string; initials: string; label: string }
> = {
  student: { id: 'student-maria', name: 'Maria Santos', initials: 'MS', label: 'Student' },
  teacher: { id: 'teacher-santos', name: 'Prof. Maria Santos', initials: 'MS', label: 'Teacher' },
  administrator: {
    id: 'admin-preview',
    name: 'Admin User',
    initials: 'AU',
    label: 'Administrator',
  },
};

const teachers = {
  santos: { id: 'teacher-santos', name: 'Prof. Maria Santos' },
  cruz: { id: 'teacher-cruz', name: 'Prof. Avery Cruz' },
  reyes: { id: 'teacher-reyes', name: 'Prof. Daniel Reyes' },
} as const;
const rooms = {
  science: { id: 'room-sci-218', name: 'SCI-218', building: 'Science Building', floor: 'Level 2' },
  engineering: {
    id: 'room-eng-204',
    name: 'ENG-204',
    building: 'Engineering Building',
    floor: 'Level 2',
  },
  newBuilding: { id: 'room-nb-405', name: 'Room 405', building: 'New Building', floor: 'Floor 4' },
} as const;
const subjects = {
  hci: { id: 'subject-hci', name: 'Human Computer Interaction' },
  database: { id: 'subject-database', name: 'Database Management Systems' },
  web: { id: 'subject-web', name: 'Web Systems' },
  networks: { id: 'subject-networks', name: 'Network Fundamentals' },
} as const;
const sections = {
  it2: { id: 'section-it-2a', name: 'BSIT 2A' },
  cs1: { id: 'section-cs-1b', name: 'BSCS 1B' },
  it3: { id: 'section-it-3a', name: 'BSIT 3A' },
} as const;

// Explicit development fixtures. These are not enrollment, reservations, validation
// results, or production identities. No clock or persistence drives this scenario.
export const schedulePreview: SchedulePreviewData = {
  occurrences: [
    {
      id: 'occ-hci-mon',
      subject: subjects.hci,
      section: sections.cs1,
      teacher: teachers.cruz,
      room: rooms.newBuilding,
      startsAt: '2026-10-12T08:00',
      endsAt: '2026-10-12T09:30',
      publication: 'published',
    },
    {
      id: 'occ-database-mon',
      subject: subjects.database,
      section: sections.it2,
      teacher: teachers.santos,
      room: rooms.science,
      startsAt: '2026-10-12T10:00',
      endsAt: '2026-10-12T11:30',
      publication: 'published',
    },
    {
      id: 'occ-networks-mon',
      subject: subjects.networks,
      section: sections.it3,
      teacher: teachers.reyes,
      room: rooms.science,
      startsAt: '2026-10-12T11:00',
      endsAt: '2026-10-12T12:00',
      publication: 'draft',
    },
    {
      id: 'occ-web-mon',
      subject: subjects.web,
      section: sections.cs1,
      teacher: teachers.santos,
      room: rooms.engineering,
      startsAt: '2026-10-12T13:00',
      endsAt: '2026-10-12T14:30',
      publication: 'published',
    },
    {
      id: 'occ-database-tue',
      subject: subjects.database,
      section: sections.it2,
      teacher: teachers.santos,
      room: rooms.science,
      startsAt: '2026-10-13T10:00',
      endsAt: '2026-10-13T11:30',
      publication: 'published',
    },
  ],
  students: [
    {
      id: 'student-maria',
      name: 'Maria Santos',
      assignmentIds: ['occ-hci-mon', 'occ-database-mon', 'occ-web-mon', 'occ-database-tue'],
    },
    { id: 'student-other', name: 'Alex Reyes', assignmentIds: ['occ-networks-mon'] },
  ],
  requests: [
    {
      id: 'request-room-access',
      assignmentId: 'occ-database-mon',
      teacherId: 'teacher-santos',
      status: 'pending',
      updatedAt: '2026-10-12T09:10',
      reason: 'Review room access requirements for this session.',
    },
    {
      id: 'request-equipment',
      assignmentId: 'occ-web-mon',
      teacherId: 'teacher-santos',
      status: 'declined',
      updatedAt: '2026-10-12T09:20',
      reason:
        'The proposed alternative lacks the required equipment. The assigned room is unchanged.',
    },
  ],
  conflicts: [
    {
      id: 'conflict-science-overlap',
      assignmentIds: ['occ-database-mon', 'occ-networks-mon'],
      status: 'open',
      reason: 'The draft Network Fundamentals session overlaps a published assignment in SCI-218.',
    },
  ],
  updates: [
    {
      id: 'update-web-room',
      assignmentId: 'occ-web-mon',
      title: 'Room assignment updated',
      detail:
        'Web Systems is assigned to ENG-204, Engineering Building · Level 2, in this sample schedule.',
    },
  ],
};

export function previewViewer(role: UserRole): ScheduleViewer {
  return role === 'administrator' ? { role } : { role, id: previewProfiles[role].id };
}
