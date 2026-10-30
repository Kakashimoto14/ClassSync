import type { ReactNode } from 'react';

export function StudentPageHeader({
  title,
  context,
  term,
  action,
}: {
  title: string;
  context?: string;
  term?: string;
  action?: ReactNode;
}) {
  return (
    <header className="student-page-header">
      <div>
        {(context || term) && (
          <p className="student-page-context">
            {context}
            {context && term && <span aria-hidden="true"> · </span>}
            {term}
          </p>
        )}
        <h1>{title}</h1>
      </div>
      {action && <div className="student-page-action">{action}</div>}
    </header>
  );
}
