import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { ClassSyncInlineSpinner } from '../loading/ClassSyncLoading';
type Props = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' | 'ghost'; children: ReactNode; loading?: boolean };
export function Button({ variant = 'primary', className = '', children, loading = false, ...props }: Props) { return <button className={`button button--${variant} ${className}`} {...props} aria-busy={loading || props['aria-busy']}>{loading && <ClassSyncInlineSpinner />}{children}</button>; }
