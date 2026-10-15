import { AlertTriangle, Check, CircleDot, Info } from 'lucide-react';
import type { StatusTone } from '../../types/ui';
const icons = { success: Check, warning: AlertTriangle, danger: AlertTriangle, info: Info, neutral: CircleDot };
export function StatusBadge({ tone, children }: { tone: StatusTone; children: string }) { const Icon = icons[tone]; return <span className={`status status--${tone}`}><Icon size={13} aria-hidden="true"/>{children}</span>; }
