import { useContext } from 'react';
import { DevelopmentRoleContext } from './development-role-context';

export function useDevelopmentRole() {
  const context = useContext(DevelopmentRoleContext);
  if (!context) throw new Error('useDevelopmentRole must be used inside DevelopmentRoleProvider');
  return context;
}
