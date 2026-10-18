import { describe, expect, it } from 'vitest';
import { dashboardPath, mobileNavigationForRole, navigationForRole, navigationOwner, rolePath, routeDefinitions } from './route-config';

describe('role aware route registry', () => {
  it('keeps saved draft details oriented in Saved Drafts and the mobile Schedule tab', () => {
    const path = '/admin/schedule-manager/drafts/596cd220-6451-414f-8460-a74abd3da359';
    expect(navigationOwner(path)).toBe('administrator.schedule-drafts');
    expect(navigationOwner(path, true)).toBe('administrator.ai-scheduling');
    expect(navigationOwner('/admin/schedule-manager/drafts', true)).toBe('administrator.ai-scheduling');
    expect(navigationOwner('/student/schedule-manager/drafts/anything')).toBeUndefined();
  });
  it('assigns unique paths and identifiers', () => {
    expect(new Set(routeDefinitions.map(route => route.path)).size).toBe(routeDefinitions.length);
    expect(new Set(routeDefinitions.map(route => route.id)).size).toBe(routeDefinitions.length);
  });

  it('keeps personal schedule routes separate from schedule management', () => {
    expect(rolePath('student', 'schedule')).toBe('/student/schedule');
    expect(rolePath('teacher', 'schedule')).toBe('/teacher/schedule');
    expect(rolePath('administrator', 'schedule-manager')).toBe('/admin/schedule-manager');
  });

  it('provides dashboard routes for exactly the initial roles', () => {
    expect(dashboardPath('student')).toBe('/student/dashboard');
    expect(dashboardPath('teacher')).toBe('/teacher/dashboard');
    expect(dashboardPath('administrator')).toBe('/admin/dashboard');
  });

  it('only puts role owned routes in each role navigation', () => {
    for (const role of ['student', 'teacher', 'administrator'] as const) {
      const navigation = navigationForRole(role).flatMap(group => group.items);
      expect(navigation.every(route => route.role === role)).toBe(true);
      expect(navigation.every(route => routeDefinitions.some(registered => registered.path === route.path))).toBe(true);
    }
    expect(navigationForRole('student').flatMap(group => group.items).some(route => route.kind === 'schedule' && route.role === 'administrator')).toBe(false);
  });

  it('keeps administrator schedule creation out of student and teacher route sets', () => {
    const manager = routeDefinitions.find(route => route.path === '/admin/schedule-manager');
    expect(manager?.role).toBe('administrator');
    expect(routeDefinitions.some(route => route.path === '/student/schedule-manager')).toBe(false);
    expect(routeDefinitions.some(route => route.path === '/teacher/schedule-manager')).toBe(false);
  });

  it('registers planned features only for their authorized roles', () => {
    expect(rolePath('student', 'registration-scanner')).toBe('/student/registration-scanner');
    expect(rolePath('administrator', 'ai-conflict-detection')).toBe('/admin/ai-conflict-detection');
    expect(rolePath('administrator', 'ai-scheduling')).toBe('/admin/ai-scheduling');
    expect(rolePath('administrator', 'institutional-rules')).toBe('/admin/institutional-rules');
    expect(routeDefinitions.some(route => route.path.startsWith('/teacher/') && route.kind === 'coming-soon')).toBe(false);
  });

  it('keeps student mobile navigation to its four primary destinations', () => {
    expect(mobileNavigationForRole('student').map(route => route.mobileLabel)).toEqual(['Home', 'Schedule', 'Rooms', 'Alerts']);
    expect(mobileNavigationForRole('student')).toHaveLength(4);
  });
});
