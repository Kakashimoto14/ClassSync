import type { GenerationInput, Section } from '../../../../packages/shared-types/src/scheduling';

export function sectionLabel(section: Section | undefined, input: GenerationInput) {
  if (!section) return 'Unknown section';
  const program = input.programs?.find((p) => p.id === section.program_id);
  return (
    section.custom_label ||
    `${program?.acronym ?? section.program_id}-${section.year_level}${section.section_letter}`
  );
}
export const draftPath = (id: string, source: 'synthetic' | 'academic' = 'synthetic') => `/admin/schedule-manager/drafts/${encodeURIComponent(id)}${source === 'academic' ? '?source=academic' : ''}`;
