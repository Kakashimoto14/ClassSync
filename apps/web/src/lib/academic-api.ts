import { env } from './env';
import { requireLiveCapability } from '../config/runtime-config';
import { appMode } from '../config/runtime-config';
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
export const listAcademicPeriods = () => academicRequest<AcademicPeriodList>(base);
export const createAcademicPeriod = (body: PeriodCreate) =>
  academicRequest<AcademicSnapshot>(base, body, 'POST');
export const loadAcademicPeriod = (id: string) =>
  academicRequest<AcademicSnapshot>(`${base}/${encodeURIComponent(id)}`);
export const saveAcademicRecord = (period: string, body: RecordWrite) =>
  academicRequest<AcademicSnapshot>(
    `${base}/${encodeURIComponent(period)}/records/${body.record.kind}/${encodeURIComponent(body.record.id!)}`,
    body,
    'PUT',
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
