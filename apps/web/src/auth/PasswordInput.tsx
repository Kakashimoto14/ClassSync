import { Eye, EyeOff } from 'lucide-react';
import { forwardRef, type InputHTMLAttributes } from 'react';

/** Password field with a show/hide toggle. The parent owns visibility so paired fields match. */
export const PasswordInput = forwardRef<
  HTMLInputElement,
  Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & {
    visible: boolean;
    onToggle?: () => void;
  }
>(function PasswordInput({ visible, onToggle, ...props }, ref) {
  return (
    <div className="entrance-password">
      <input ref={ref} type={visible ? 'text' : 'password'} {...props} />
      {onToggle && (
        <button
          type="button"
          aria-label="Show password"
          aria-pressed={visible}
          disabled={props.disabled}
          onClick={onToggle}
        >
          {visible ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
        </button>
      )}
    </div>
  );
});
