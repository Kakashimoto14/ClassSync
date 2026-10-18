import type { LucideIcon } from 'lucide-react';
import { matchPath } from 'react-router-dom';
import {
  Bell,
  BookOpen,
  Bot,
  Building2,
  CalendarDays,
  ClipboardCheck,
  ClipboardList,
  DoorOpen,
  FileBarChart,
  FileSearch,
  LayoutDashboard,
  MapPin,
  Megaphone,
  ShieldAlert,
  UsersRound,
} from 'lucide-react';
import type { UserRole } from '../types/ui';

export type ScreenKind =
  | 'dashboard'
  | 'schedule'
  | 'schedule-create'
  | 'schedule-drafts'
  | 'schedule-draft-detail'
  | 'calendar'
  | 'conflicts'
  | 'conflict-detail'
  | 'requests'
  | 'request-create'
  | 'request-detail'
  | 'report-issue'
  | 'rooms'
  | 'room-detail'
  | 'buildings'
  | 'building-detail'
  | 'academic-list'
  | 'academic-detail'
  | 'academic-manage'
  | 'reports'
  | 'notifications'
  | 'announcements'
  | 'profile'
  | 'settings'
  | 'audit'
  | 'coming-soon';
export type PlannedFeature =
  'registration-scanner' | 'ai-conflict-detection' | 'ai-scheduling' | 'institutional-rules';
export type RouteId = `${UserRole}.${string}`;
export interface RouteDefinition {
  id: RouteId;
  path: `/${string}`;
  role: UserRole;
  title: string;
  description: string;
  kind: ScreenKind;
  roomMode?: 'directory' | 'availability';
  navigationGroup?: string;
  navigationLabel?: string;
  icon: LucideIcon;
  mobileLabel?: string;
  plannedFeature?: PlannedFeature;
  academicKind?: 'programs' | 'subjects' | 'sections' | 'faculty' | 'resources' | 'offerings' | 'constraints';
}
const make = (definition: RouteDefinition): RouteDefinition => definition;
export const routeDefinitions = [
  make({
    id: 'student.dashboard',
    path: '/student/dashboard',
    role: 'student',
    title: 'Dashboard',
    description: 'Your next class, room, and schedule updates.',
    kind: 'dashboard',
    navigationGroup: 'Overview',
    navigationLabel: 'Dashboard',
    icon: LayoutDashboard,
    mobileLabel: 'Home',
  }),
  make({
    id: 'student.schedule',
    path: '/student/schedule',
    role: 'student',
    title: 'My Schedule',
    description: 'Your classes, instructors, and assigned classrooms for this week.',
    kind: 'schedule',
    navigationGroup: 'Academic',
    navigationLabel: 'My Schedule',
    icon: CalendarDays,
    mobileLabel: 'Schedule',
  }),
  make({
    id: 'student.calendar',
    path: '/student/calendar',
    role: 'student',
    title: 'My Calendar',
    description: 'Browse your classes and schedule changes by date.',
    kind: 'calendar',
    icon: CalendarDays,
  }),
  make({
    id: 'student.registration-scanner',
    path: '/student/registration-scanner',
    role: 'student',
    title: 'Registration Form Scanner',
    description:
      'Planned OVRF and registration-form scanning with reviewable subject and section extraction.',
    kind: 'coming-soon',
    navigationGroup: 'Academic',
    navigationLabel: 'Registration Form Scanner',
    icon: FileSearch,
    plannedFeature: 'registration-scanner',
  }),
  make({
    id: 'student.rooms',
    path: '/student/rooms',
    role: 'student',
    title: 'Room Directory',
    description: 'Find classroom locations and facilities.',
    kind: 'rooms',
    roomMode: 'directory',
    navigationGroup: 'Rooms',
    navigationLabel: 'Rooms',
    icon: MapPin,
    mobileLabel: 'Rooms',
  }),
  make({
    id: 'student.find-room',
    path: '/student/find-room',
    role: 'student',
    title: 'Find a Room',
    description: 'Compare classroom resources and review availability limitations.',
    kind: 'rooms',
    roomMode: 'availability',
    navigationGroup: 'Rooms',
    navigationLabel: 'Find a Room',
    icon: DoorOpen,
  }),
  make({
    id: 'student.notifications',
    path: '/student/notifications',
    role: 'student',
    title: 'Notifications',
    description: 'Schedule and classroom updates that affect you.',
    kind: 'notifications',
    navigationGroup: 'Communication',
    navigationLabel: 'Notifications',
    icon: Bell,
    mobileLabel: 'Alerts',
  }),
  make({
    id: 'student.announcements',
    path: '/student/announcements',
    role: 'student',
    title: 'Announcements',
    description: 'Academic notices and scheduling information.',
    kind: 'announcements',
    navigationGroup: 'Communication',
    navigationLabel: 'Announcements',
    icon: Megaphone,
  }),
  make({
    id: 'student.room-detail',
    path: '/student/rooms/detail',
    role: 'student',
    title: 'Room Details',
    description: 'Location, facilities, and recorded demo assignments.',
    kind: 'room-detail',
    icon: Building2,
  }),
  make({
    id: 'student.profile',
    path: '/student/profile',
    role: 'student',
    title: 'Profile',
    description: 'Your account and academic information.',
    kind: 'profile',
    icon: UsersRound,
  }),
  make({
    id: 'student.settings',
    path: '/student/settings',
    role: 'student',
    title: 'Settings',
    description: 'Manage your account and notification preferences.',
    kind: 'settings',
    icon: BookOpen,
  }),

  make({
    id: 'teacher.dashboard',
    path: '/teacher/dashboard',
    role: 'teacher',
    title: 'Dashboard',
    description: 'Your teaching day, assigned rooms, and requests.',
    kind: 'dashboard',
    navigationGroup: 'Overview',
    navigationLabel: 'Dashboard',
    icon: LayoutDashboard,
    mobileLabel: 'Home',
  }),
  make({
    id: 'teacher.schedule',
    path: '/teacher/schedule',
    role: 'teacher',
    title: 'My Teaching Schedule',
    description: 'Your classes, sections, assigned rooms, and updates.',
    kind: 'schedule',
    navigationGroup: 'Academic',
    navigationLabel: 'My Schedule',
    icon: CalendarDays,
    mobileLabel: 'Schedule',
  }),
  make({
    id: 'teacher.calendar',
    path: '/teacher/calendar',
    role: 'teacher',
    title: 'Teaching Calendar',
    description: 'Browse your teaching assignments and room changes by date.',
    kind: 'calendar',
    icon: CalendarDays,
  }),
  make({
    id: 'teacher.availability',
    path: '/teacher/room-availability',
    role: 'teacher',
    title: 'Room Availability',
    description: 'Check planned classroom availability for a teaching period.',
    kind: 'rooms',
    roomMode: 'availability',
    navigationGroup: 'Rooms',
    navigationLabel: 'Room Availability',
    icon: DoorOpen,
  }),
  make({
    id: 'teacher.find-room',
    path: '/teacher/find-room',
    role: 'teacher',
    title: 'Room Directory',
    description: 'Find classroom locations, capacity, and equipment.',
    kind: 'rooms',
    roomMode: 'directory',
    navigationGroup: 'Rooms',
    navigationLabel: 'Room Directory',
    mobileLabel: 'Rooms',
    icon: MapPin,
  }),
  make({
    id: 'teacher.requests',
    path: '/teacher/change-requests',
    role: 'teacher',
    title: 'Classroom Change Requests',
    description: 'Track your submitted requests and administrator decisions.',
    kind: 'requests',
    navigationGroup: 'Requests',
    navigationLabel: 'Change Requests',
    icon: ClipboardList,
    mobileLabel: 'Requests',
  }),
  make({
    id: 'teacher.request-create',
    path: '/teacher/change-requests/new',
    role: 'teacher',
    title: 'Request a Classroom Change',
    description: 'Ask an administrator to review a change to your assigned classroom.',
    kind: 'request-create',
    icon: ClipboardList,
  }),
  make({
    id: 'teacher.request-detail',
    path: '/teacher/change-requests/detail',
    role: 'teacher',
    title: 'Request Details',
    description: 'Review the submitted request and its current status.',
    kind: 'request-detail',
    icon: ClipboardList,
  }),
  make({
    id: 'teacher.report-issue',
    path: '/teacher/report-issue',
    role: 'teacher',
    title: 'Report a Classroom Issue',
    description: 'Send an issue to the administrator for review.',
    kind: 'report-issue',
    navigationGroup: 'Requests',
    navigationLabel: 'Report Issue',
    icon: ShieldAlert,
  }),
  make({
    id: 'teacher.notifications',
    path: '/teacher/notifications',
    role: 'teacher',
    title: 'Notifications',
    description: 'Teaching schedule, room, and request updates.',
    kind: 'notifications',
    navigationGroup: 'Communication',
    navigationLabel: 'Notifications',
    icon: Bell,
    mobileLabel: 'Alerts',
  }),
  make({
    id: 'teacher.announcements',
    path: '/teacher/announcements',
    role: 'teacher',
    title: 'Announcements',
    description: 'Academic notices and scheduling information.',
    kind: 'announcements',
    navigationGroup: 'Communication',
    navigationLabel: 'Announcements',
    icon: Megaphone,
  }),
  make({
    id: 'teacher.room-detail',
    path: '/teacher/rooms/detail',
    role: 'teacher',
    title: 'Room Details',
    description: 'Location, facilities, and recorded demo assignments.',
    kind: 'room-detail',
    icon: Building2,
  }),
  make({
    id: 'teacher.profile',
    path: '/teacher/profile',
    role: 'teacher',
    title: 'Profile',
    description: 'Your account and teaching information.',
    kind: 'profile',
    icon: UsersRound,
  }),
  make({
    id: 'teacher.settings',
    path: '/teacher/settings',
    role: 'teacher',
    title: 'Settings',
    description: 'Manage your account and notification preferences.',
    kind: 'settings',
    icon: BookOpen,
  }),

  make({
    id: 'administrator.dashboard',
    path: '/admin/dashboard',
    role: 'administrator',
    title: 'Dashboard',
    description: 'Monitor today’s schedules, rooms, conflicts, and requests.',
    kind: 'dashboard',
    navigationGroup: 'Overview',
    navigationLabel: 'Dashboard',
    icon: LayoutDashboard,
    mobileLabel: 'Home',
  }),
  make({
    id: 'administrator.schedule-manager',
    path: '/admin/schedule-manager',
    role: 'administrator',
    title: 'Schedule Manager',
    description: 'Review, validate, and manage official academic schedules.',
    kind: 'schedule',
    navigationGroup: 'Scheduling',
    icon: CalendarDays,
    mobileLabel: 'Schedule',
  }),
  make({
    id: 'administrator.schedule-create',
    path: '/admin/schedule-manager/create',
    role: 'administrator',
    title: 'Generate Schedule',
    description: 'Prepare a schedule draft and review its required checks.',
    kind: 'schedule-create',
    icon: CalendarDays,
  }),
  make({
    id: 'administrator.schedule-drafts',
    path: '/admin/schedule-manager/drafts',
    role: 'administrator',
    title: 'Saved Drafts',
    description: 'Reopen validated timetables saved for administrator review.',
    kind: 'schedule-drafts',
    navigationGroup: 'Scheduling',
    navigationLabel: 'Saved Drafts',
    icon: ClipboardList,
  }),
  make({
    id: 'administrator.schedule-draft-detail',
    path: '/admin/schedule-manager/drafts/:draftId',
    role: 'administrator',
    title: 'Saved Draft',
    description: 'Review a saved timetable. Drafts are not published schedules.',
    kind: 'schedule-draft-detail',
    icon: CalendarDays,
  }),
  make({
    id: 'administrator.calendar',
    path: '/admin/calendar',
    role: 'administrator',
    title: 'Published Timetables',
    description: 'View campus schedules and changes by date.',
    kind: 'calendar',
    navigationGroup: 'Scheduling',
    navigationLabel: 'Published Timetables',
    icon: CalendarDays,
  }),
  make({
    id: 'administrator.conflicts',
    path: '/admin/conflicts',
    role: 'administrator',
    title: 'Conflict Center',
    description: 'Investigate scheduling conflicts and review safe resolution options.',
    kind: 'conflicts',
    navigationGroup: 'Scheduling',
    navigationLabel: 'Conflicts',
    icon: ShieldAlert,
    mobileLabel: 'Conflicts',
  }),
  make({
    id: 'administrator.ai-conflict-detection',
    path: '/admin/ai-conflict-detection',
    role: 'administrator',
    title: 'AI Conflict Detection',
    description:
      'Independent constraint validation. AI explanations are planned.',
    kind: 'conflicts',
    navigationGroup: 'Scheduling',
    icon: Bot,
  }),
  make({
    id: 'administrator.ai-scheduling',
    path: '/admin/ai-scheduling',
    role: 'administrator',
    title: 'AI-Powered Scheduling', mobileLabel: 'Generate',
    description:
      'Generate, validate and save a constraint-based weekly timetable.',
    kind: 'schedule-create',
    navigationGroup: 'Scheduling',
    navigationLabel: 'AI-Powered Scheduling',
    icon: CalendarDays,
  }),
  make({
    id: 'administrator.conflict-detail',
    path: '/admin/conflicts/detail',
    role: 'administrator',
    title: 'Conflict Details',
    description: 'Inspect conflicting records and available resolution choices.',
    kind: 'conflict-detail',
    icon: ShieldAlert,
  }),
  make({
    id: 'administrator.requests',
    path: '/admin/requests',
    role: 'administrator',
    title: 'Classroom Requests',
    description: 'Review classroom change requests and issue reports.',
    kind: 'requests',
    navigationGroup: 'Scheduling',
    navigationLabel: 'Requests',
    icon: ClipboardList,
  }),
  make({
    id: 'administrator.request-detail',
    path: '/admin/requests/detail',
    role: 'administrator',
    title: 'Request Details',
    description: 'Review request context, status history, and decision options.',
    kind: 'request-detail',
    icon: ClipboardList,
  }),
  make({
    id: 'administrator.teachers',
    path: '/admin/teachers',
    role: 'administrator',
    title: 'Faculty',
    description: 'Review teacher records, assignments, and availability.',
    kind: 'academic-manage',
    academicKind: 'faculty',
    navigationGroup: 'Academic Setup',
    navigationLabel: 'Faculty',
    icon: UsersRound,
  }),
  make({
    id: 'administrator.students',
    path: '/admin/students',
    role: 'administrator',
    title: 'Students',
    description: 'Review student records and schedule context.',
    kind: 'academic-list',
    navigationGroup: 'Academic Setup',
    navigationLabel: 'Students',
    icon: UsersRound,
  }),
  make({
    id: 'administrator.subjects',
    path: '/admin/subjects',
    role: 'administrator',
    title: 'Subjects',
    description: 'Review subjects and scheduling requirements.',
    kind: 'academic-manage',
    academicKind: 'subjects',
    navigationGroup: 'Academic Setup',
    navigationLabel: 'Subjects',
    icon: BookOpen,
  }),
  make({
    id: 'administrator.sections',
    path: '/admin/sections',
    role: 'administrator',
    title: 'Sections',
    description: 'Review section assignments, advisers, and schedule status.',
    kind: 'academic-manage',
    academicKind: 'sections',
    navigationGroup: 'Academic Setup',
    navigationLabel: 'Sections',
    icon: UsersRound,
  }),
  make({
    id: 'administrator.academic-data', path: '/admin/academic', role: 'administrator', title: 'Academic Management',
    description: 'Manage saved academic periods and scheduling inputs.', kind: 'academic-manage', academicKind: 'programs',
    navigationGroup: 'Academic Setup', navigationLabel: 'Academic Years / Semesters', icon: BookOpen,
  }),
  make({
    id: 'administrator.programs', path: '/admin/programs', role: 'administrator', title: 'Programs',
    description: 'Configure program names and section naming policies for a saved period.', navigationGroup: 'Academic Setup', navigationLabel: 'Programs', kind: 'academic-manage', academicKind: 'programs', icon: BookOpen,
  }),
  make({
    id: 'administrator.offerings', path: '/admin/offerings', role: 'administrator', title: 'Subject Offerings',
    description: 'Assign subjects, sections, eligible faculty and classrooms.', navigationGroup: 'Academic Setup', navigationLabel: 'Subject Offerings', kind: 'academic-manage', academicKind: 'offerings', icon: BookOpen,
  }),
  make({
    id: 'administrator.resource-metadata', path: '/admin/academic/resources', role: 'administrator', title: 'Resource Metadata',
    description: 'Enter resource constraints with provenance. Provisional locations remain separate from suitability.', kind: 'academic-manage', academicKind: 'resources', icon: Building2,
  }),
  make({
    id: 'administrator.scheduling-constraints', path: '/admin/scheduling-constraints', role: 'administrator', title: 'Scheduling Constraints',
    description: 'Set allowed teaching windows, workload rules and locked assignments.', kind: 'academic-manage', academicKind: 'constraints', icon: CalendarDays,
  }),
  make({
    id: 'administrator.academic-detail',
    path: '/admin/academic/details',
    role: 'administrator',
    title: 'Academic Record Details',
    description: 'Review related subjects, sections, people, and scheduled classes.',
    kind: 'academic-detail',
    icon: UsersRound,
  }),
  make({
    id: 'administrator.rooms',
    path: '/admin/rooms',
    role: 'administrator',
    title: 'Room Directory',
    description: 'Review classroom capacity, facilities, and resource status.',
    kind: 'rooms',
    roomMode: 'directory',
    navigationGroup: 'Campus',
    navigationLabel: 'Rooms',
    icon: MapPin,
  }),
  make({
    id: 'administrator.room-detail',
    path: '/admin/rooms/detail',
    role: 'administrator',
    title: 'Room Details',
    description: 'Review location, resource status, facilities, and scheduled classes.',
    kind: 'room-detail',
    icon: Building2,
  }),
  make({
    id: 'administrator.buildings',
    path: '/admin/buildings',
    role: 'administrator',
    title: 'Buildings & Areas',
    description: 'Review campus buildings and their classroom resources.',
    kind: 'buildings',
    navigationGroup: 'Campus',
    navigationLabel: 'Buildings',
    icon: Building2,
  }),
  make({
    id: 'administrator.building-detail',
    path: '/admin/buildings/detail',
    role: 'administrator',
    title: 'Building Details',
    description: 'Review a building and its classroom resources.',
    kind: 'building-detail',
    icon: Building2,
  }),
  make({
    id: 'administrator.availability',
    path: '/admin/room-availability',
    role: 'administrator',
    title: 'Room Availability',
    description: 'Check planned classroom availability by time and requirements.',
    kind: 'rooms',
    roomMode: 'availability',
    navigationGroup: 'Campus',
    navigationLabel: 'Room Availability',
    icon: DoorOpen,
  }),
  make({
    id: 'administrator.reports',
    path: '/admin/reports',
    role: 'administrator',
    title: 'Reports',
    description: 'Operational summaries to support academic scheduling decisions.',
    kind: 'reports',
    navigationGroup: 'Insights',
    navigationLabel: 'Reports',
    icon: FileBarChart,
  }),
  make({
    id: 'administrator.utilization',
    path: '/admin/utilization',
    role: 'administrator',
    title: 'Room Utilization',
    description: 'Review scheduled classroom usage patterns.',
    kind: 'reports',
    navigationGroup: 'Insights',
    navigationLabel: 'Room Utilization',
    icon: FileBarChart,
  }),
  make({
    id: 'administrator.notifications',
    mobileLabel: 'Alerts',
    path: '/admin/notifications',
    role: 'administrator',
    title: 'Notifications',
    description: 'Review schedule, room, request, and system updates.',
    kind: 'notifications',
    navigationGroup: 'Communication',
    navigationLabel: 'Notifications',
    icon: Bell,
  }),
  make({
    id: 'administrator.announcements',
    path: '/admin/announcements',
    role: 'administrator',
    title: 'Announcements',
    description: 'Review academic notices and prepare communications.',
    kind: 'announcements',
    navigationGroup: 'Communication',
    navigationLabel: 'Announcements',
    icon: Megaphone,
  }),
  make({
    id: 'administrator.audit',
    path: '/admin/audit-logs',
    role: 'administrator',
    title: 'Audit Logs',
    description: 'Review administrative actions and schedule decisions.',
    kind: 'audit',
    navigationGroup: 'System',
    navigationLabel: 'Audit Logs',
    icon: ClipboardList,
  }),
  make({
    id: 'administrator.institutional-rules',
    path: '/admin/institutional-rules',
    role: 'administrator',
    title: 'Institutional Scheduling Rules',
    description: 'Planned authorized management of institutional scheduling rules.',
    kind: 'coming-soon',
    navigationGroup: 'System',
    navigationLabel: 'Institutional Scheduling Rules',
    icon: ClipboardCheck,
    plannedFeature: 'institutional-rules',
  }),
  make({
    id: 'administrator.settings',
    path: '/admin/settings',
    role: 'administrator',
    title: 'Settings',
    description: 'Manage system preferences and notification options.',
    kind: 'settings',
    navigationGroup: 'System',
    navigationLabel: 'Settings',
    icon: BookOpen,
  }),
  make({
    id: 'administrator.profile',
    path: '/admin/profile',
    role: 'administrator',
    title: 'Profile',
    description: 'Your administrator account information.',
    kind: 'profile',
    icon: UsersRound,
  }),
] as const satisfies readonly RouteDefinition[];

export const routesByPath = new Map<string, RouteDefinition>(
  routeDefinitions.map((route) => [route.path, route]),
);
export function dashboardPath(role: UserRole): string {
  return (
    routeDefinitions.find((route) => route.role === role && route.kind === 'dashboard')?.path ??
    '/student/dashboard'
  );
}
export function rolePath(role: UserRole, suffix: string): string {
  return (
    routeDefinitions.find((route) => route.id === `${role}.${suffix}`)?.path ?? dashboardPath(role)
  );
}
export function navigationForRole(role: UserRole): { title: string; items: RouteDefinition[] }[] {
  const items = routeDefinitions.filter(
    (route) => route.role === role && route.navigationGroup && route.navigationLabel,
  );
  const groups = new Map<string, RouteDefinition[]>();
  for (const item of items) {
    const group = item.navigationGroup!;
    groups.set(group, [...(groups.get(group) ?? []), item]);
  }
  return [...groups].map(([title, groupItems]) => ({ title, items: groupItems }));
}

const mobileNavigationIds: Record<UserRole, readonly RouteId[]> = {
  student: ['student.dashboard', 'student.schedule', 'student.rooms', 'student.notifications'],
  teacher: [
    'teacher.dashboard',
    'teacher.schedule',
    'teacher.find-room',
    'teacher.requests',
  ],
  administrator: [
    'administrator.dashboard',
    'administrator.ai-scheduling',
    'administrator.conflicts',
    'administrator.notifications',
  ],
};

export function mobileNavigationForRole(role: UserRole): RouteDefinition[] {
  return mobileNavigationIds[role].flatMap((id) =>
    routeDefinitions.filter((route) => route.id === id),
  );
}

// Explicit ownership preserves section context without prefix-matching unrelated routes.
const navigationParents: Partial<Record<RouteId, RouteId>> = {
  'administrator.schedule-manager': 'administrator.ai-scheduling',
  'student.room-detail': 'student.rooms',
  'teacher.room-detail': 'teacher.find-room',
  'student.calendar': 'student.schedule',
  'student.registration-scanner': 'student.schedule',
  'student.find-room': 'student.rooms',
  'student.announcements': 'student.notifications',
  'teacher.calendar': 'teacher.schedule',
  'teacher.availability': 'teacher.find-room',
  'teacher.request-create': 'teacher.requests',
  'teacher.request-detail': 'teacher.requests',
  'teacher.report-issue': 'teacher.requests',
  'teacher.announcements': 'teacher.notifications',
  'administrator.schedule-create': 'administrator.ai-scheduling',
  'administrator.schedule-drafts': 'administrator.schedule-manager',
  'administrator.schedule-draft-detail': 'administrator.schedule-drafts',
  'administrator.calendar': 'administrator.schedule-manager',
  'administrator.conflict-detail': 'administrator.conflicts',
  'administrator.ai-conflict-detection': 'administrator.conflicts',
  'administrator.request-detail': 'administrator.requests',
  'administrator.room-detail': 'administrator.rooms',
  'administrator.building-detail': 'administrator.buildings',
  'administrator.academic-detail': 'administrator.sections',
  'administrator.programs': 'administrator.academic-data',
  'administrator.offerings': 'administrator.academic-data',
  'administrator.resource-metadata': 'administrator.academic-data',
  'administrator.scheduling-constraints': 'administrator.academic-data',
  'administrator.utilization': 'administrator.reports',
  'administrator.announcements': 'administrator.notifications',
};

export function navigationOwner(path: string, mobile = false): RouteId | undefined {
  const pathname = path.split(/[?#]/, 1)[0].replace(/\/+$/, '');
  let route = routesByPath.get(pathname) ?? routeDefinitions.find(
    (item) => item.path.includes('/:') && matchPath({ path: item.path, end: true }, pathname),
  );
  const visited = new Set<RouteId>();
  while (route && !visited.has(route.id)) {
    visited.add(route.id);
    if (mobile ? mobileNavigationIds[route.role].includes(route.id) : route.navigationLabel)
      return route.id;
    const parent = navigationParents[route.id];
    route = parent ? routeDefinitions.find((item) => item.id === parent) : undefined;
  }
  return undefined;
}
