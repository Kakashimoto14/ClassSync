import { expect, it } from 'vitest';
import type { RouteObject } from 'react-router-dom';
import { createAppRoutes } from '../routes/app-routes';

function routePaths(routes: RouteObject[]): string[] {
  return routes.flatMap((route) => [
    ...(route.path ? [route.path] : []),
    ...routePaths(route.children ?? []),
  ]);
}

it.each([
  ['institutional', false],
  ['sandbox', true],
  ['presentation', true],
] as const)('exposes development routes in %s mode only when allowed', (mode, expected) => {
  const paths = routePaths(createAppRoutes(mode));

  expect(paths.includes('dev/design-system')).toBe(expected);
  expect(paths.includes('dev/role-preview')).toBe(expected);
  expect(paths).toContain('auth/login');
});
