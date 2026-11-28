// Imported only by lazy pages so none of it joins the main entry.
import { institutionalRequest } from './institutional-api';
import { provisionalCdmRooms } from '../data/cdm-room-inventory';

export const issueCategories = {
  equipment: 'Equipment',
  electrical: 'Electrical or lighting',
  furniture: 'Furniture',
  cleanliness: 'Cleanliness',
  safety: 'Safety',
  other: 'Other',
} as const;
export const issueStatusLabel = {
  open: 'Open',
  in_progress: 'In progress',
  resolved: 'Resolved',
  dismissed: 'Dismissed',
} as const;
export type IssueCategory = keyof typeof issueCategories;
export type IssueStatus = keyof typeof issueStatusLabel;

export interface FacilityIssue {
  id: string;
  room_id: string;
  occurrence_id: string | null;
  occurrence_date: string | null;
  category: IssueCategory;
  description: string;
  status: IssueStatus;
  revision: number;
  resolution_note: string | null;
  linked_restriction_id: string | null;
  created_at: string;
  updated_at: string;
  history?: Array<{
    revision: number;
    to_status: IssueStatus;
    note: string | null;
    created_at: string;
  }>;
}

export const schedulableRooms = provisionalCdmRooms.filter((room) => room.schedulable);
export const issueRoom = (id: string) => provisionalCdmRooms.find((room) => room.id === id);
export const issueTime = (value: string) =>
  new Intl.DateTimeFormat('en-PH', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'Asia/Manila',
  }).format(new Date(value));

export const listIssues = (role: 'teacher' | 'administrator', signal?: AbortSignal) =>
  institutionalRequest<{ issues: FacilityIssue[] }>('timetables/issues', { role, signal });
export const reportIssue = (body: Record<string, string>) =>
  institutionalRequest<FacilityIssue>('timetables/issues', {
    role: 'teacher',
    method: 'POST',
    body,
  });
export const transitionIssue = (
  id: string,
  body: {
    expected_revision: number;
    status: Exclude<IssueStatus, 'open'>;
    note?: string;
    linked_restriction_id?: string;
  },
) =>
  institutionalRequest<FacilityIssue>(`timetables/issues/${encodeURIComponent(id)}/transition`, {
    role: 'administrator',
    method: 'POST',
    body,
  });
