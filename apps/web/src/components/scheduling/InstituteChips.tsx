import { INSTITUTES } from '../../lib/program-scope';
import './week-grid.css';

/** `All / ICS / IBE / ITE` toggle chips; an empty value means every institute. */
export function InstituteChips({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="institute-chips" role="group" aria-label="Institute">
      {['', ...INSTITUTES].map((code) => (
        <button
          key={code || 'all'}
          type="button"
          aria-pressed={value === code}
          onClick={() => onChange(code)}
        >
          {code || 'All'}
        </button>
      ))}
    </div>
  );
}
