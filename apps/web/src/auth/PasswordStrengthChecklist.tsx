import { CheckCircle2, XCircle } from 'lucide-react';
import { passwordRules } from './password-strength';

export function PasswordStrengthChecklist({
  password,
  confirmPassword,
}: {
  password: string;
  confirmPassword: string;
}) {
  const rules = [
    ...passwordRules.map((rule) => ({ ...rule, complete: rule.matches(password) })),
    {
      label: 'Passwords match',
      complete: confirmPassword.length > 0 && password === confirmPassword,
    },
  ];
  return (
    <ul className="password-strength-checklist" aria-label="Password requirements" role="list">
      {rules.map(({ label, complete }) => {
        const Icon = complete ? CheckCircle2 : XCircle;
        return (
          <li key={label} data-complete={complete}>
            <Icon aria-hidden="true" size={15} />
            <span>{label}</span>
          </li>
        );
      })}
    </ul>
  );
}
