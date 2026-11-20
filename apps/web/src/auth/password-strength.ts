const passwordRules = [
  { label: 'At least 12 characters', matches: (password: string) => password.length >= 12 },
  { label: 'Uppercase letter (A–Z)', matches: (password: string) => /[A-Z]/.test(password) },
  { label: 'Lowercase letter (a–z)', matches: (password: string) => /[a-z]/.test(password) },
  { label: 'Number (0–9)', matches: (password: string) => /[0-9]/.test(password) },
  { label: 'Special character (!@#$...)', matches: (password: string) => /[^A-Za-z0-9]/.test(password) },
];

export function passwordStrengthComplete(password: string, confirmPassword: string) {
  return passwordRules.every((rule) => rule.matches(password)) &&
    confirmPassword.length > 0 && password === confirmPassword;
}

export { passwordRules };
