import type { ReactNode } from 'react';
import { DialogSurface } from './DialogSurface';
export function Modal(props: { title: string; onClose: () => void; children: ReactNode }) {
  return <DialogSurface variant="modal" {...props} />;
}
