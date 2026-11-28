import { AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import type { ReactNode } from 'react';
import type { StatusTone } from '../../types/ui';
const icons = { success: CheckCircle2, warning: AlertTriangle, danger: AlertTriangle, info: Info, neutral: Info };
export function Alert({ tone, title, children, action }: { tone: StatusTone; title: string; children: string; action?: ReactNode }) { const Icon = icons[tone]; return <div className={`alert alert--${tone}`} role={tone === 'danger' ? 'alert' : 'status'}><Icon aria-hidden="true"/><div><strong>{title}</strong><p>{children}</p>{action}</div></div>; }
