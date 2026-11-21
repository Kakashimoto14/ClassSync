import { describe, expect, it } from 'vitest';
import { formatLoginIdentifier, formatStudentNumber, isValidAccountEmail } from './student-number';

describe('student and email form normalization', () => {
  it('formats seven digits as YY-NNNNN and caps excess digits', () => {
    expect(formatStudentNumber('2498097')).toBe('24-98097');
    expect(formatStudentNumber('24 98097 88')).toBe('24-98097');
  });

  it('formats numeric login input while leaving email input untouched', () => {
    expect(formatLoginIdentifier('2498097')).toBe('24-98097');
    expect(formatLoginIdentifier('Student.Demo@gmail.com')).toBe('Student.Demo@gmail.com');
  });

  it('accepts valid personal and school domains and rejects malformed input', () => {
    expect(isValidAccountEmail(' student.demo@gmail.com ')).toBe(true);
    expect(isValidAccountEmail('Juan.Delacruz@student.pnm.edu.ph')).toBe(true);
    expect(isValidAccountEmail('foo@@gmail.com')).toBe(false);
    expect(isValidAccountEmail('foo@localhost')).toBe(false);
  });
});
