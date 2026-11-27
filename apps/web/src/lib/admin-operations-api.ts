// Imported only by lazy Administrator pages so none of it joins the main entry.
import { institutionalRequest } from './institutional-api';
import type { AcademicSnapshot } from './academic-api';
import type { RoomRestriction } from '../../../../packages/shared-types/src/scheduling';

type Status = 'active' | 'inactive' | 'unverified';

const send = <T>(path: string, body?: unknown, method = body === undefined ? 'GET' : 'POST') =>
  institutionalRequest<T>(path, { body, method, role: 'administrator', timeout: 50000 });
const periodPath = (period: string) => `academic/periods/${encodeURIComponent(period)}`;

export const bulkRosterStatus = (
  period: string,
  body: { expected_period_revision: number; student_ids: string[]; enrollment_status: Status },
) =>
  send<{ updated: number; skipped: number; period_revision: number }>(
    `${periodPath(period)}/roster/bulk-status`,
    body,
  );

export interface RosterImportRow {
  line: number;
  student_id: string;
  full_name: string;
  email: string;
  section_label: string;
  enrollment_status: string;
  action: 'create_new' | 'enroll_existing';
  note: string;
  errors: string[];
}
export interface RosterImportPreview {
  rows: RosterImportRow[];
  total: number;
  invalid: number;
  create_new: number;
  enroll_existing: number;
  rows_hash: string | null;
  period_revision: number;
}
export const previewRosterImport = (period: string, csv: string) =>
  send<RosterImportPreview>(`${periodPath(period)}/roster/import/preview`, { csv });
export const commitRosterImport = (
  period: string,
  body: { csv: string; rows_hash: string; expected_period_revision: number },
) => send<{ imported: number; created: number; enrolled_existing: number }>(
  `${periodPath(period)}/roster/import/commit`,
  body,
);

export const cloneAcademicPeriod = (period: string, title: string) =>
  send<AcademicSnapshot>(`${periodPath(period)}/clone`, { title });
export const archiveAcademicPeriod = (period: string, expected_revision: number) =>
  send<AcademicSnapshot>(`${periodPath(period)}/archive`, { expected_revision });

export interface UtilizationGroup {
  name: string;
  rooms: number;
  available_minutes: number;
  restricted_minutes: number;
  booked_minutes: number;
  utilization: number | null;
}
export interface SchedulingReport {
  period: { id: string; title: string; revision: number; archived_at: string | null };
  published: { version: string; revision: number; created_at: string } | null;
  timezone: string;
  basis: { effective_start: string; effective_end: string; instructional_dates: number } | null;
  rooms: Array<{
    id: string;
    name: string;
    building: string;
    room_type: string;
    operating_minutes: number;
    restricted_minutes: number;
    available_minutes: number;
    booked_minutes: number;
    utilization: number | null;
  }>;
  buildings: UtilizationGroup[];
  room_types: UtilizationGroup[];
  faculty: Array<{
    id: string;
    name: string;
    active: boolean;
    weekly_minutes: number;
    sessions: number;
    max_weekly_minutes: number | null;
    load: number | null;
  }>;
  programs: Array<{
    id: string;
    program: string;
    institute: string;
    sections: number;
    offerings: number;
    students: number;
    sessions: number;
    weekly_minutes: number;
  }>;
  institutes: Array<{
    institute: string;
    programs: number;
    sections: number;
    offerings: number;
    students: number;
    sessions: number;
    weekly_minutes: number;
  }>;
  sections: Array<{
    id: string;
    label: string;
    program: string;
    active_days: number;
    sessions: number;
    one_class_days: number;
    max_sessions_per_day: number;
    longest_span_minutes: number;
    idle_minutes: number;
  }>;
}
export const loadSchedulingReport = (period: string) =>
  send<SchedulingReport>(`timetables/reports/${encodeURIComponent(period)}`);

export type SavedRestriction = Omit<RoomRestriction, 'expected_revision' | 'status'> & {
  status: 'active' | 'cancelled';
  revision: number;
};
export interface RestrictionImpact {
  total: number;
  sessions: Array<{
    date: string;
    starts_at: string;
    ends_at: string;
    subject: { code: string; name: string };
    section: { name: string };
    teacher: { name: string };
  }>;
}
export const listRestrictions = () =>
  send<{ restrictions: SavedRestriction[] }>('timetables/restrictions');
export const preflightRestriction = (body: RoomRestriction) =>
  send<RestrictionImpact>('timetables/restrictions/preflight', body);
export const saveRestriction = (body: RoomRestriction) =>
  send<SavedRestriction>(`timetables/restrictions/${encodeURIComponent(body.id)}`, body, 'PUT');
