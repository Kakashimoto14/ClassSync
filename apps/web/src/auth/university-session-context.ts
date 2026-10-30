import { createContext, useContext } from 'react';
import type { UserRole } from '../types/ui';
import type { UniversitySession } from './university-session';

export interface UniversitySessionContextValue {
  available: boolean;
  state: UniversitySession;
  refresh: (role?: UserRole) => void;
  signOut: () => void;
}
export const UniversitySessionContext = createContext<UniversitySessionContextValue>({
  available: false,
  state: { status: 'unavailable' },
  refresh: () => {},
  signOut: () => {},
});
export function useUniversitySession() {
  return useContext(UniversitySessionContext);
}
