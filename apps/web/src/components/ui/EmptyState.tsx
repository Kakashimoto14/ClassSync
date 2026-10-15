import { Inbox } from 'lucide-react';
export function EmptyState({ title = 'No results found', detail = 'Adjust filters or try again.' }: { title?: string; detail?: string }) { return <div className="empty-state"><Inbox aria-hidden="true"/><strong>{title}</strong><span>{detail}</span></div>; }
