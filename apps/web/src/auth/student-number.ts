export function formatStudentNumber(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, 7);
  return digits.length > 2 ? `${digits.slice(0, 2)}-${digits.slice(2)}` : digits;
}

export function formatLoginIdentifier(raw: string): string {
  if (/^\d/.test(raw) && !/[a-z@]/i.test(raw)) return formatStudentNumber(raw);
  return raw;
}

export function normalizeAccountEmail(raw: string): string {
  return raw.trim().toLowerCase();
}

export function isValidAccountEmail(raw: string): boolean {
  const email = normalizeAccountEmail(raw);
  return /^(?=.{3,320}$)(?=.{1,64}@)[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/.test(email);
}
