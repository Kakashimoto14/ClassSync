import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import './page.css';

export interface Kpi {
  label: string;
  value: ReactNode;
  hint?: string;
  to?: string;
}

/** Headline counts. Linked tiles form a navigation list; plain ones a description list. */
export function KpiStrip({ label, items }: { label: string; items: Kpi[] }) {
  if (items.every((item) => !item.to))
    return (
      <dl className="kpi-strip" aria-label={label}>
        {items.map((item) => (
          <div className="kpi-strip__tile" key={item.label}>
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
            {item.hint && <dd className="kpi-strip__hint">{item.hint}</dd>}
          </div>
        ))}
      </dl>
    );
  return (
    <nav aria-label={label}>
      <ul className="kpi-strip">
        {items.map((item) => (
          <li key={item.label}>
            <Link className="kpi-strip__tile" to={item.to!}>
              <span className="kpi-strip__label">{item.label}</span>{' '}
              <strong className="kpi-strip__value">{item.value}</strong>{' '}
              {item.hint && <span className="kpi-strip__hint">{item.hint}</span>}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
