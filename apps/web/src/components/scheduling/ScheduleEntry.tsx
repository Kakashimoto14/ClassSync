import { Clock3, MapPin } from 'lucide-react';
import type { ScheduleOccurrence } from '../../data/schedule-preview';
import { formatPreviewDate, formatTimeRange } from '../../lib/schedule-preview';
import { StatusBadge } from '../ui/StatusBadge';

export function ScheduleEntry({
  occurrence,
  showDate = false,
  showPublication = false,
  featured = false,
}: {
  occurrence: ScheduleOccurrence;
  showDate?: boolean;
  showPublication?: boolean;
  featured?: boolean;
}) {
  if (featured)
    return (
      <article
        className="schedule-entry schedule-entry--featured"
        data-assignment-id={occurrence.id}
      >
        <h3>{occurrence.subject.name}</h3>
        <div className="featured-time">
          <Clock3 size={16} aria-hidden="true" />
          {showDate && <span>{formatPreviewDate(occurrence.startsAt)}</span>}
          <time dateTime={occurrence.startsAt}>{formatTimeRange(occurrence)}</time>
        </div>
        <div className="featured-location">
          <MapPin size={20} aria-hidden="true" />
          <div>
            <strong>{occurrence.room.name}</strong>
            <span>
              {occurrence.room.building}
              {occurrence.room.floor && ` · ${occurrence.room.floor}`}
            </span>
          </div>
        </div>
        <dl className="featured-people">
          <div>
            <dt>Professor</dt>
            <dd>{occurrence.teacher.name}</dd>
          </div>
          <div>
            <dt>Section</dt>
            <dd>{occurrence.section.name}</dd>
          </div>
        </dl>
        {showPublication && (
          <StatusBadge tone={occurrence.publication === 'published' ? 'info' : 'neutral'}>
            {
              { published: 'Published', draft: 'Draft', cancelled: 'Cancelled' }[
                occurrence.publication
              ]
            }
          </StatusBadge>
        )}
      </article>
    );
  return (
    <article className="schedule-entry" data-assignment-id={occurrence.id}>
      <div className="schedule-entry__time">
        {showDate && <span>{formatPreviewDate(occurrence.startsAt)}</span>}
        <time dateTime={occurrence.startsAt}>{formatTimeRange(occurrence)}</time>
      </div>
      <div className="schedule-entry__body">
        <strong>{occurrence.subject.name}</strong>
        <span className="schedule-entry__location">
          <MapPin size={16} aria-hidden="true" />
          <span>
            <b>{occurrence.room.name}</b> · {occurrence.room.building}
            {occurrence.room.floor && ` · ${occurrence.room.floor}`}
          </span>
        </span>
        <span>
          {occurrence.section.name} · {occurrence.teacher.name}
        </span>
      </div>
      {showPublication && (
        <StatusBadge tone={occurrence.publication === 'published' ? 'info' : 'neutral'}>
          {
            { published: 'Published', draft: 'Draft', cancelled: 'Cancelled' }[
              occurrence.publication
            ]
          }
        </StatusBadge>
      )}
    </article>
  );
}
