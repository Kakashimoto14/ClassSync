import { useId } from 'react';
import type { ScheduleOccurrence } from '../../data/schedule-preview';
import { EmptyState } from '../ui/EmptyState';
import { ScheduleEntry } from './ScheduleEntry';

export function ScheduleAgenda({
  title,
  occurrences,
  emptyMessage,
  showPublication = false,
}: {
  title: string;
  occurrences: readonly ScheduleOccurrence[];
  emptyMessage: string;
  showPublication?: boolean;
}) {
  const titleId = useId();
  return (
    <section className="schedule-agenda" aria-labelledby={titleId}>
      <div className="section-head">
        <h2 id={titleId}>{title}</h2>
        <span className="muted">
          {occurrences.length} {occurrences.length === 1 ? 'class' : 'classes'}
        </span>
      </div>
      {occurrences.length ? (
        <ol className="schedule-agenda__list">
          {occurrences.map((occurrence) => (
            <li key={occurrence.id}>
              <ScheduleEntry occurrence={occurrence} showPublication={showPublication} />
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState title={emptyMessage} detail="This reflects the selected demo day." />
      )}
    </section>
  );
}
