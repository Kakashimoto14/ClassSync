import { describe, expect, it } from 'vitest';
import { readinessActionForIssue } from './readiness-navigation';

describe('readiness destinations', () => {
  it.each([
    ['missing_offerings', '/admin/offerings?period=term-1'],
    ['missing_operating_hours', '/admin/scheduling-constraints?period=term-1'],
    ['section_without_offerings', '/admin/offerings?period=term-1'],
    ['teacher_availability_missing', '/admin/teachers?period=term-1'],
    ['room_availability_unverified', '/admin/academic/resources?period=term-1'],
  ])('routes %s to its setup page', (code, expected) => {
    expect(
      readinessActionForIssue({ code, message: 'actual readiness message', severity: 'blocking' }, 'term-1'),
    ).toMatchObject({ to: expected, known: true });
  });

  it('uses the readiness screen for unknown codes and encodes the period', () => {
    expect(
      readinessActionForIssue(
        { code: 'unexpected/code', message: 'keep this diagnostic visible', severity: 'blocking' },
        'term & 1',
      ),
    ).toMatchObject({
      label: 'Review scheduling readiness',
      to: '/admin/ai-scheduling?period=term+%26+1#readiness-issues',
      known: false,
    });
  });
});
