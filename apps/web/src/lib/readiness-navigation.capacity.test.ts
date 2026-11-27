import { describe, expect, it } from 'vitest';
import { readinessActionForIssue } from './readiness-navigation';

describe('capacity bottleneck readiness links', () => {
  it('uses the server-named setup screen and labels new bottleneck codes', () => {
    const action = readinessActionForIssue(
      {
        severity: 'blocking', code: 'room_pool_capacity', message: 'Labs are full.',
        action_path: '/admin/academic/resources',
      },
      'period-a',
    );
    expect(action).toEqual({
      label: 'Add or widen room windows', to: '/admin/academic/resources?period=period-a',
      known: true,
    });
    const faculty = readinessActionForIssue(
      { severity: 'blocking', code: 'faculty_pool_capacity', message: 'Over the cap.' },
      'p',
    );
    expect(faculty.to).toBe('/admin/teachers?period=p');
  });
});
