import type { Assignment, GenerationInput, Offering, Section } from '../../../../packages/shared-types/src/scheduling';

export function sectionLabel(section: Section | undefined, input: GenerationInput) {
  if (!section) return 'Unknown section';
  const program = input.programs?.find((p) => p.id === section.program_id);
  return (
    section.custom_label ||
    `${program?.acronym ?? section.program_id}-${section.year_level}${section.section_letter}`
  );
}
export const draftPath = (id: string, source: 'synthetic' | 'academic' = 'synthetic') => `/admin/schedule-manager/drafts/${encodeURIComponent(id)}${source === 'academic' ? '?source=academic' : ''}`;

export const DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
export const clockLabel = (minutes: number) =>
  `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
export const slotLabel = (a: Assignment) => `${DAY_NAMES[a.day]?.slice(0, 3)} ${clockLabel(a.start)}`;
export const roomLabel = (id: string, input: GenerationInput) =>
  input.rooms?.find((room) => room.id === id)?.name ?? 'Unknown room';

/** `Subject · Section · Mon 08:00 · NB-204`, never a record identifier. */
export function assignmentLabel(a: Assignment, input: GenerationInput) {
  const offering = input.offerings?.find((o) => o.id === a.offering_id);
  const section = input.sections?.find((s) => s.id === a.section_id);
  return [
    offering?.subject_name ?? 'Unknown subject',
    sectionLabel(section, input),
    slotLabel(a),
    roomLabel(a.room_id, input),
  ].join(' · ');
}

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
/** Server and advisor prose with session ids replaced by their labels. */
export function readableText(text: string, assignments: Assignment[], input: GenerationInput) {
  return (
    [...assignments]
      // Very short ids could also be ordinary words, so they are left alone.
      .filter((a) => a.id.length >= 6)
      .sort((a, b) => b.id.length - a.id.length)
      .reduce((value, a) => value.split(a.id).join(assignmentLabel(a, input)), text)
      .replace(UUID, 'record')
  );
}

const SESSION_LABELS = {
  lecture: 'Lecture',
  computer_lab: 'Computer lab',
  science_lab: 'Science lab',
  athletic: 'Athletic',
} as const;
export type SessionType = keyof typeof SESSION_LABELS;
export function sessionType(offering?: Offering): { type: SessionType; label: string } {
  const activity = offering?.activity_type;
  const room = offering?.required_room_type;
  const type: SessionType =
    activity === 'computer_lab_instruction' || room === 'computer_lab'
      ? 'computer_lab'
      : activity === 'bse_science_instruction' || room === 'science_lab'
        ? 'science_lab'
        : activity === 'pahfit' || activity === 'sports' || activity === 'rotc' || room === 'athletic_space'
          ? 'athletic'
          : 'lecture';
  // Assemblies and special bookings share the neutral colour but are not called lectures.
  const label =
    activity === 'assembly'
      ? 'Assembly'
      : activity === 'special_booking'
        ? 'Special booking'
        : SESSION_LABELS[type];
  return { type, label };
}
