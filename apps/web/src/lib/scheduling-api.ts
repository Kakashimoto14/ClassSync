import type {
  GenerationInput,
  GenerationResult,
  ReadinessResult,
  ValidationResult,
  SaveDraftRequest,
  DraftDetail,
  DraftList,
} from '../../../../packages/shared-types/src/scheduling';
import { env } from './env';

export type { GenerationInput, GenerationResult, ValidationResult };
export type { DraftDetail, DraftList, SaveDraftRequest };
export const schedulingSandboxEnabled = import.meta.env.DEV;

async function request<T>(operation: string, body?: unknown): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 50000);
  try {
    const response = await fetch(`${env.apiBaseUrl}/scheduling/sandbox/${operation}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: controller.signal,
    });
    if (!response.headers.get('content-type')?.includes('application/json')) {
      throw new Error('Scheduling service unavailable. No server confirmation was received.');
    }
    const payload = await response.json();
    if (!response.ok) {
      const detail = payload.error?.message ?? payload.detail ?? 'Scheduling request failed.';
      throw new Error(
        Array.isArray(detail)
          ? detail
              .map(
                (d: { loc?: string[]; msg?: string }) => `${d.loc?.join('.') ?? 'input'}: ${d.msg}`,
              )
              .join('; ')
          : String(detail),
      );
    }
    return payload.data as T;
  } catch (error) {
    if (error instanceof TypeError) throw new Error('Could not reach the scheduling service. No server confirmation was received.');
    if (error instanceof Error && error.name === 'AbortError')
      throw new Error(
        'The request timed out without confirmation. If saving, check Saved Drafts before retrying.',
      );
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export const loadSchedulingScenario = (infeasible = false) =>
  request<GenerationInput>(`scenario?infeasible=${infeasible}`);
export const generateWeeklySchedule = (input: GenerationInput) =>
  request<GenerationResult>('generate', input);
export const checkSchedulingInputs = (input: unknown) =>
  request<ReadinessResult>('readiness', input);
export const validateWeeklySchedule = (
  input: GenerationInput,
  assignments: GenerationResult['assignments'],
) => request<ValidationResult>('validate', { inputs: input, assignments });

export const saveSchedulingDraft = (body: SaveDraftRequest, source: 'synthetic' | 'academic' = 'synthetic') => request<DraftDetail>(`${source === 'academic' ? 'academic/' : ''}drafts`, body);
export const listSchedulingDrafts = (offset = 0, source: 'synthetic' | 'academic' = 'synthetic') => request<DraftList>(`${source === 'academic' ? 'academic/' : ''}drafts?limit=25&offset=${offset}`);
export const loadSchedulingDraft = (id: string, source: 'synthetic' | 'academic' = 'synthetic') => request<DraftDetail>(`${source === 'academic' ? 'academic/' : ''}drafts/${encodeURIComponent(id)}`);
