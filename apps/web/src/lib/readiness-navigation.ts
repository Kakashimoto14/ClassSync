import type { ReadinessIssue } from '../../../../packages/shared-types/src/scheduling';

export type ReadinessAction = {
  label: string;
  to: string;
  known: boolean;
};

const routes = {
  academic: '/admin/academic',
  curriculum: '/admin/subjects',
  faculty: '/admin/teachers',
  resources: '/admin/academic/resources',
  sections: '/admin/sections',
  constraints: '/admin/scheduling-constraints',
  offerings: '/admin/offerings',
  readiness: '/admin/ai-scheduling',
} as const;

const issueRoutes: Record<string, { label: string; path: string }> = {
  missing_sections: { label: 'Set up sections', path: routes.sections },
  missing_offerings: { label: 'Set up offerings', path: routes.offerings },
  missing_inputs: { label: 'Review scheduling inputs', path: routes.readiness },
  duplicate_identity: { label: 'Review academic records', path: routes.academic },
  missing_reference: { label: 'Review academic references', path: routes.academic },
  section_naming: { label: 'Review section details', path: routes.sections },
  invalid_preference: { label: 'Review scheduling preferences', path: routes.constraints },
  missing_academic_calendar: { label: 'Set up calendar', path: routes.academic },
  missing_operating_hours: { label: 'Set operating hours', path: routes.constraints },
  section_without_offerings: { label: 'Assign offerings', path: routes.offerings },
  population_unverified: { label: 'Review section data', path: routes.sections },
  cohort_assignment_unverified: { label: 'Review curriculum', path: routes.curriculum },
  section_identity_unverified: { label: 'Review section data', path: routes.sections },
  population_reference_missing: { label: 'Review section data', path: routes.sections },
  section_verification_reference_missing: {
    label: 'Review section data',
    path: routes.sections,
  },
  inactive_reference: { label: 'Review offerings', path: routes.offerings },
  curriculum_association: { label: 'Review curriculum', path: routes.curriculum },
  curriculum_unreviewed: { label: 'Review curriculum', path: routes.curriculum },
  contact_minutes_unverified: { label: 'Review curriculum', path: routes.curriculum },
  curriculum_reference_missing: { label: 'Review curriculum', path: routes.curriculum },
  contact_minutes_reference_missing: { label: 'Review curriculum', path: routes.curriculum },
  term_offering_unverified: { label: 'Review offerings', path: routes.offerings },
  offering_reference_missing: { label: 'Review offerings', path: routes.offerings },
  offering_override_unverified: { label: 'Review offerings', path: routes.offerings },
  synthetic_faculty: { label: 'Review faculty', path: routes.faculty },
  program_association: { label: 'Review offerings', path: routes.offerings },
  missing_faculty: { label: 'Assign faculty', path: routes.offerings },
  faculty_eligibility: { label: 'Review faculty', path: routes.faculty },
  teacher_availability_missing: { label: 'Set faculty availability', path: routes.faculty },
  faculty_workload_unverified: { label: 'Review faculty workload', path: routes.faculty },
  faculty_verification_missing: { label: 'Review faculty', path: routes.faculty },
  missing_room_eligibility: { label: 'Choose room candidates', path: routes.offerings },
  room_reference: { label: 'Review room resources', path: routes.resources },
  noninstitutional_room: { label: 'Review room resources', path: routes.resources },
  room_availability_unverified: { label: 'Review room resources', path: routes.resources },
  missing_weekly_minutes: { label: 'Review offerings', path: routes.offerings },
  missing_patterns: { label: 'Review offerings', path: routes.offerings },
  insufficient_faculty_workload: { label: 'Review faculty workload', path: routes.faculty },
  capacity_not_required: { label: 'Review capacity data', path: routes.offerings },
  session_requirement: { label: 'Review offerings', path: routes.offerings },
  scope_not_complete: { label: 'Review period scope', path: routes.constraints },
  operating_windows_unverified: { label: 'Review operating hours', path: routes.constraints },
  shared_scope_unverified: { label: 'Review period scope', path: routes.constraints },
  inactive_records: { label: 'Review inactive records', path: routes.offerings },
  input_contract: { label: 'Review scheduling inputs', path: routes.readiness },
  insufficient_weekly_time: { label: 'Review teaching windows', path: routes.constraints },
  insufficient_distinct_days: { label: 'Review teaching days', path: routes.constraints },
  no_legal_placement: { label: 'Review teaching windows', path: routes.constraints },
  no_eligible_room: { label: 'Review room requirements', path: routes.offerings },
  room_pool_capacity: { label: 'Add or widen room windows', path: routes.resources },
  faculty_pool_capacity: { label: 'Review faculty capacity', path: routes.faculty },
  section_time_capacity: { label: 'Review section load', path: routes.sections },
  excluded_space_selected: { label: 'Remove excluded spaces', path: routes.offerings },
  operating_days_outside_calendar: { label: 'Review calendar days', path: routes.academic },
};

export function readinessActionForIssue(issue: ReadinessIssue, periodId: string): ReadinessAction {
  const match = issueRoutes[issue.code];
  // The server names the exact setup screen for capacity bottlenecks; prefer it when present.
  const path = issue.action_path ?? match?.path ?? routes.readiness;
  const label = match?.label ?? 'Review scheduling readiness';
  const params = new URLSearchParams({ period: periodId });
  const anchor = path === routes.readiness ? '#readiness-issues' : '';
  return { label, to: `${path}?${params.toString()}${anchor}`, known: Boolean(match) };
}
