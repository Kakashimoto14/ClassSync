export function formatStudentNumber(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 7);
  return digits.length > 2 ? `${digits.slice(0, 2)}-${digits.slice(2)}` : digits;
}

export function formatLoginIdentifier(raw: string, previous = ''): string {
  // A trailing separator is useful while someone types an email such as 23-juan@example.com.
  if (/^\d{2}-$/.test(raw)) return raw;

  const studentNumberInput = /^\d{0,7}$/.test(raw) || /^\d{2}-\d{0,5}$/.test(raw);
  if (studentNumberInput) return formatStudentNumber(raw);

  const extendedAutoFormattedPrefix = /^\d{2}-\d{1,5}$/.test(previous)
    && raw.length > previous.length
    && raw.startsWith(previous);
  if (extendedAutoFormattedPrefix && /^\d{2}-/.test(raw))
    return `${raw.slice(0, 2)}${raw.slice(3)}`;
  return raw;
}

export function normalizeAccountEmail(raw: string): string {
  return raw.trim().toLowerCase();
}

export function isValidAccountEmail(raw: string): boolean {
  const email = normalizeAccountEmail(raw);
  return /^(?=.{3,320}$)(?=.{1,64}@)[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/.test(email);
}
