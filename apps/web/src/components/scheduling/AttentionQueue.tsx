import { Link } from 'react-router-dom';
import { useId } from 'react';
import { ArrowRight } from 'lucide-react';
import { StatusBadge } from '../ui/StatusBadge';

export interface AttentionItem {
  id: string;
  title: string;
  detail: string;
  context?: string;
  status: 'Blocking conflict' | 'Pending decision';
  href: string;
  action: string;
}
export function AttentionQueue({
  items,
  title = 'Needs attention',
  emptyMessage = 'No attention items in the supplied demo records. This is not a live validation result.',
}: {
  items: readonly AttentionItem[];
  title?: string;
  emptyMessage?: string;
}) {
  const titleId = useId();
  return (
    <section className="attention-queue" aria-labelledby={titleId}>
      <div className="section-head">
        <h2 id={titleId}>{title}</h2>
        <span className="muted">
          {items.length} {items.length === 1 ? 'item' : 'items'}
        </span>
      </div>
      {items.length ? (
        <ol>
          {items.map((item) => (
            <li key={item.id}>
              <StatusBadge tone={item.status === 'Blocking conflict' ? 'danger' : 'warning'}>
                {item.status}
              </StatusBadge>
              <h3>{item.title}</h3>
              {item.context && <p className="attention-queue__context">{item.context}</p>}
              <p>{item.detail}</p>
              <Link className="button attention-queue__action" to={item.href}>
                {item.action} <ArrowRight size={16} aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">{emptyMessage}</p>
      )}
    </section>
  );
}
