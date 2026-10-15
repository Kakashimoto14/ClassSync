import { dashboardPath, routeDefinitions } from '../routes/route-config';
import type { UserRole } from '../types/ui';

export interface LoginValidationErrors {
  email?: string;
  password?: string;
}

export function validateLogin(email: string, password: string): LoginValidationErrors {
  const errors: LoginValidationErrors = {};
  if (!email.trim()) errors.email = 'Enter your university email address.';
  else if (!/^\S+@\S+\.\S+$/.test(email)) errors.email = 'Enter a valid email address.';
  if (!password) errors.password = 'Enter your password.';
  return errors;
}

export function isRoleOwnedPath(role: UserRole, path: string): boolean {
  return routeDefinitions.some(route => route.role === role && route.path === path);
}

export function demoDestination(role: UserRole, requestedPath: string | null): string {
  return requestedPath && isRoleOwnedPath(role, requestedPath) ? requestedPath : dashboardPath(role);
}
