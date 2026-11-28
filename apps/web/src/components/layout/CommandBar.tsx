import type { ReactNode } from 'react';
import './page.css';

/** A single filter and command row. */
export function CommandBar({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="command-bar" role="group" aria-label={label}>
      {children}
    </div>
  );
}

/** A compact field: the label stays available to assistive technology only. */
export function CommandField({
  label,
  wide = false,
  children,
}: {
  label: string;
  wide?: boolean;
  children: ReactNode;
}) {
  return (
    <label className={`command-field${wide ? ' command-field--wide' : ''}`}>
      <span className="visually-hidden">{label}</span>
      {children}
    </label>
  );
}
