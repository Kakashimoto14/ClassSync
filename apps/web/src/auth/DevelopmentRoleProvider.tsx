import { useState, type ReactNode } from 'react';
import { DevelopmentRoleContext } from './development-role-context';
import type { UserRole } from '../types/ui';

export function DevelopmentRoleProvider({ children }: { children: ReactNode }) {
  const [role, setRole] = useState<UserRole | null>(null);
  return <DevelopmentRoleContext.Provider value={{ role, startDemo: setRole, signOut: () => setRole(null) }}>{children}</DevelopmentRoleContext.Provider>;
}
