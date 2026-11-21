import { dashboardPath, routeDefinitions } from '../routes/route-config';
import type { UserRole } from '../types/ui';

export interface LoginValidationErrors {
  email?: string;
  password?: string;
}

export function validateLogin(email: string, password: string): LoginValidationErrors {
  const errors: LoginValidationErrors = {};
  if (!email.trim()) errors.email = 'Enter your student number or email address.';
  else if (!/^\S+@\S+\.\S+$/.test(email) && !/^[0-9]{2}-[0-9]{5}$/.test(email))
    errors.email = 'Enter a valid email address or student number.';
  if (!password) errors.password = 'Enter your password.';
  return errors;
}

export function isRoleOwnedPath(role: UserRole, path: string): boolean {
  const pathname = path.split(/[?#]/, 1)[0].replace(/\/+$/, '');
  return routeDefinitions.some((route) => route.role === role && route.path === pathname);
}

export function workspaceDestination(role: UserRole, requested: string | null): string {
  if (
    requested?.startsWith('/') &&
    !requested.startsWith('//') &&
    !/[\\\s]/.test(requested) &&
    isRoleOwnedPath(role, requested)
  )
    return requested;
  return dashboardPath(role);
}

export function demoDestination(role: UserRole, requestedPath: string | null): string {
  return requestedPath && isRoleOwnedPath(role, requestedPath)
    ? requestedPath
    : dashboardPath(role);
}
