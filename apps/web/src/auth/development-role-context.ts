import { createContext } from 'react';
import type { UserRole } from '../types/ui';

export interface DevelopmentRoleContextValue { role: UserRole | null; startDemo: (role: UserRole) => void; signOut: () => void; }
export const DevelopmentRoleContext = createContext<DevelopmentRoleContextValue | null>(null);
