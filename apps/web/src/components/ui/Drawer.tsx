import type { ReactNode } from 'react';
import { DialogSurface } from './DialogSurface';
export function Drawer(props: { title: string; onClose: () => void; children: ReactNode }) {
  return <DialogSurface variant="drawer" {...props} />;
}
