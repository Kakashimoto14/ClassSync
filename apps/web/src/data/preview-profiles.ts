import type { UserRole } from '../types/ui';

// Kept apart from schedule-preview so the app shell does not pull sample schedules
// and the campus room catalog into the main entry chunk.
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
