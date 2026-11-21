import { describe, expect, it } from 'vitest';
import { formatLoginIdentifier, formatStudentNumber, isValidAccountEmail } from './student-number';

describe('student and email form normalization', () => {
  it('formats seven digits as YY-NNNNN and caps excess digits', () => {
    expect(formatStudentNumber('2498097')).toBe('24-98097');
    expect(formatStudentNumber('24 98097 88')).toBe('24-98097');
  });

  it('formats student numbers and preserves numeric-prefix emails while typing or pasting', () => {
    expect(formatLoginIdentifier('2498097')).toBe('24-98097');
    expect(formatLoginIdentifier('24-98097')).toBe('24-98097');
    expect(formatLoginIdentifier('23juan@gmail.com')).toBe('23juan@gmail.com');
    expect(formatLoginIdentifier('2301425@yahoo.com')).toBe('2301425@yahoo.com');
    expect(formatLoginIdentifier('2024.student@outlook.com')).toBe('2024.student@outlook.com');
    expect(formatLoginIdentifier('23-juan@example.com')).toBe('23-juan@example.com');
    expect(formatLoginIdentifier('20-01425@example.com')).toBe('20-01425@example.com');
    expect(formatLoginIdentifier('23-juan@gmail.com')).toBe('23-juan@gmail.com');
    expect(formatLoginIdentifier('Student.Demo@gmail.com')).toBe('Student.Demo@gmail.com');
  });

  it('only removes an auto-inserted number separator when a numeric prefix becomes an email', () => {
    expect(formatLoginIdentifier('23-', '23')).toBe('23-');
    expect(formatLoginIdentifier('23-j', '23-')).toBe('23-j');
    expect(formatLoginIdentifier('230')).toBe('23-0');
    expect(formatLoginIdentifier('23-0', '230')).toBe('23-0');
    expect(formatLoginIdentifier('23-0j', '23-0')).toBe('230j');
    expect(formatLoginIdentifier('23-0@', '23-0')).toBe('230@');
  });

  it('accepts valid personal and school domains and rejects malformed input', () => {
    expect(isValidAccountEmail(' student.demo@gmail.com ')).toBe(true);
    expect(isValidAccountEmail('Juan.Delacruz@student.pnm.edu.ph')).toBe(true);
    expect(isValidAccountEmail('foo@@gmail.com')).toBe(false);
    expect(isValidAccountEmail('foo@localhost')).toBe(false);
  });
});
