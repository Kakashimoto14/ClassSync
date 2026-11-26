import { env } from './env';
import { requireLiveCapability } from '../config/runtime-config';
import { appMode } from '../config/runtime-config';
import { firebaseApp } from './firebase';
import { institutionalRequest } from './institutional-api';
import type {
  AcademicPeriodList,
  AcademicSnapshot,
  AcademicReadiness,
  RecordWrite,
  PeriodCreate,
  GenerationResult,
} from '../../../../packages/shared-types/src/scheduling';
export type {
  AcademicSnapshot,
  AcademicReadiness,
  RecordWrite,
  RecordEnvelope,
  AcademicPeriod,
} from '../../../../packages/shared-types/src/scheduling';
export type AcademicKind = NonNullable<RecordWrite['record']['kind']>;
export type AcademicRecord = RecordWrite['record'] & { id: string; kind: AcademicKind };

async function academicRequest<T>(path: string, body?: unknown, method = 'GET'): Promise<T> {
  if (appMode === 'institutional')
    return institutionalRequest<T>(path, { body, method, role: 'administrator', timeout: 50000 });
  requireLiveCapability();
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 50000);
  try {
    const response = await fetch(`${env.apiBaseUrl}/${path}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    }).catch(() => {
      throw new Error('Could not reach the academic service. No save or generation was confirmed.');
    });
    if (!response.headers.get('content-type')?.includes('application/json'))
      throw new Error('Academic service unavailable. Check the running services, then retry.');
    const payload = await response.json();
    if (!response.ok) {
      const detail = payload.error?.message ?? payload.detail ?? 'Academic request failed.';
      if (Array.isArray(detail))
        throw new Error(
          detail
            .map((d: { loc?: string[]; msg: string }) => `${d.loc?.join('.')}: ${d.msg}`)
            .join('; '),
        );
      if (typeof detail === 'object')
        throw new Error(
          detail.issues?.map((i: { message: string }) => i.message).join('; ') ??
            'Academic inputs are not ready. Recheck readiness.',
        );
      throw new Error(String(detail));
    }
    return payload.data as T;
  } finally {
    window.clearTimeout(timeout);
  }
}
export const academicWorkspaceEnabled = appMode !== 'presentation';
const prefix = appMode === 'sandbox' ? 'sandbox/' : '';
const base = `academic/${prefix}periods`;
const pendingAcademicReads = new Map<string, Promise<unknown>>();

async function dedupeAcademicRead<T>(path: string): Promise<T> {
  let key = path;
  if (appMode === 'institutional' && firebaseApp) {
    const { getAuth } = await import('firebase/auth');
    key = `${getAuth(firebaseApp).currentUser?.uid ?? 'signed-out'}:${path}`;
  }
  const existing = pendingAcademicReads.get(key);
  if (existing) return existing as Promise<T>;
  const pending = academicRequest<T>(path);
  pendingAcademicReads.set(key, pending);
  const clear = () => {
    if (pendingAcademicReads.get(key) === pending) pendingAcademicReads.delete(key);
  };
  void pending.then(clear, clear);
  return pending;
}

// Archived broken periods stay in the database for audit history and are never selectable.
const ARCHIVED_PERIOD_TITLE_PREFIX = 'Archived invalid period · ';

export const listAcademicPeriods = async (): Promise<AcademicPeriodList> => {
  const list = await dedupeAcademicRead<AcademicPeriodList>(base);
  // A response without a list is passed through unchanged, never turned into "no periods".
  if (!list.periods) return list;
  return {
    ...list,
    periods: list.periods.filter(
      (period) => !period.title.startsWith(ARCHIVED_PERIOD_TITLE_PREFIX),
    ),
  };
};
export const createAcademicPeriod = (body: PeriodCreate) =>
  academicRequest<AcademicSnapshot>(base, body, 'POST');
export const loadAcademicPeriod = (id: string) =>
  dedupeAcademicRead<AcademicSnapshot>(`${base}/${encodeURIComponent(id)}`);
export const saveAcademicRecord = (period: string, body: RecordWrite) =>
  academicRequest<AcademicSnapshot>(
    `${base}/${encodeURIComponent(period)}/records/${body.record.kind}/${encodeURIComponent(body.record.id!)}`,
    body,
    'PUT',
  );
export const deleteAcademicRecord = (period: string, kind: AcademicKind, id: string, revision: number) =>
  academicRequest<AcademicSnapshot>(
    `${base}/${encodeURIComponent(period)}/records/${kind}/${encodeURIComponent(id)}?expected_revision=${revision}`,
    undefined,
    'DELETE',
  );
export interface AcademicRosterPage {
  items: Array<{
    student_id: string;
    display_name: string | null;
    registered_email: string | null;
    enrollment_status: 'active' | 'inactive' | 'unverified';
    section_id: string;
    section_label: string;
    year_level: number;
  }>;
  total: number;
  limit: number;
  offset: number;
  period_revision: number;
  sections: Array<{ id: string; year_level: number; label: string; active: boolean }>;
}
export interface RosterStudentWrite {
  expected_period_revision: number;
  student_id: string;
  full_name: string;
  email: string;
  year_level: number;
  section_id: string;
  enrollment_status: 'active' | 'inactive' | 'unverified';
}
export const loadAcademicRoster = (period: string, filters: {
  limit?: number; offset?: number; search?: string; year_level?: number; section_id?: string;
}) => {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') query.set(key, String(value));
  }
  return academicRequest<AcademicRosterPage>(
    `academic/periods/${encodeURIComponent(period)}/roster?${query.toString()}`,
  );
};
export const createAcademicRosterStudent = (period: string, body: RosterStudentWrite) =>
  academicRequest<{ created: true }>(
    `academic/periods/${encodeURIComponent(period)}/roster`, body, 'POST',
  );
export const updateAcademicRosterStudent = (
  period: string, studentId: string, body: RosterStudentWrite,
) => academicRequest<{ updated: true }>(
  `academic/periods/${encodeURIComponent(period)}/roster/${encodeURIComponent(studentId)}`,
  body,
  'PUT',
);
export const deleteAcademicRosterStudent = (
  period: string, studentId: string, expectedPeriodRevision: number,
) => academicRequest<{ deleted: true }>(
  `academic/periods/${encodeURIComponent(period)}/roster/${encodeURIComponent(studentId)}` +
    `?expected_period_revision=${expectedPeriodRevision}`,
  undefined,
  'DELETE',
);
export const checkAcademicReadiness = (period: string) =>
  academicRequest<AcademicReadiness>(
    `scheduling/${prefix}academic/${encodeURIComponent(period)}/readiness`,
  );
export const generateAcademicSchedule = (period: string, revision: number) =>
  academicRequest<GenerationResult>(
    `scheduling/${prefix}academic/${encodeURIComponent(period)}/generate`,
    { expected_revision: revision },
    'POST',
  );

export interface CurriculumCatalog {
  status: string;
  versions: Array<{
    id: string;
    institute: string;
    program: string;
    entry_cohort: string;
    source_pdf: string;
    printed_curriculum_ay: string;
    source_sha256: string;
    source_archive_member: string;
  }>;
  courses: Array<{
    id: string;
    curriculum_version_id: string;
    subject_code: string;
    subject_title: string;
    year_level: string;
    semester: string;
    program: string;
    lec_hours_printed: string;
    lab_hours_printed: string;
    units_printed: string;
    prerequisite_printed: string;
    pdf_page: string;
  }>;
  program_ids: Record<string, string>;
}
export const loadCurriculumCatalog = () =>
  academicRequest<CurriculumCatalog>(`academic/${prefix}curriculum-catalog`);
