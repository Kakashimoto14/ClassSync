import type { ReactNode } from 'react';
import './page.css';

/** Collapsed provenance, revision and reference details. */
export function MetaDetails({
  summary = 'Record details',
  items,
  children,
}: {
  summary?: string;
  items?: Array<[string, ReactNode]>;
  children?: ReactNode;
}) {
  return (
    <details className="meta-details">
      <summary>{summary}</summary>
      {items && (
        <dl>
          {items.map(([term, value]) => (
            <div key={term} style={{ display: 'contents' }}>
              <dt>{term}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
      {children}
    </details>
  );
}
