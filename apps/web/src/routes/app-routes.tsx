import type { RouteObject } from 'react-router-dom';
import { lazy, Suspense, type ReactNode } from 'react';
import { AppLayout } from '../layouts/AppLayout';
import { appMode } from '../config/runtime-config';
import { developmentRoutesAvailable, type AppMode } from '../config/app-mode';
import { AuthPage } from '../pages/AuthPage';
import { ForbiddenPage, RoleProviderLayout, RoleRoute } from './RouteGuard';
import { routeDefinitions } from './route-config';

const EmailActionPage = lazy(() =>
  import('../pages/EmailActionPage').then((module) => ({ default: module.EmailActionPage })),
);
const DesignSystemPage = lazy(() =>
  import('../pages/DesignSystemPage').then((module) => ({ default: module.DesignSystemPage })),
);
const DevelopmentRolePreviewPage = lazy(() =>
  import('../pages/DevelopmentRolePreviewPage').then((module) => ({ default: module.DevelopmentRolePreviewPage })),
);
const NotFoundPage = lazy(() =>
  import('../pages/NotFoundPage').then((module) => ({ default: module.NotFoundPage })),
);

function loadRoute(element: ReactNode) {
  return <Suspense fallback={<p className="workspace-card" role="status">Opening this page…</p>}>{element}</Suspense>;
}

export function createAppRoutes(mode: AppMode): RouteObject[] {
  const developmentRoutes: RouteObject[] = developmentRoutesAvailable(mode)
    ? [
        { path: 'dev/design-system', element: loadRoute(<DesignSystemPage />) },
        { path: 'dev/role-preview', element: loadRoute(<DevelopmentRolePreviewPage />) },
      ]
    : [];

  return [
    {
      element: <RoleProviderLayout />,
      children: [
        {
          element: <AppLayout />,
          children: [
            { index: true, element: <AuthPage /> },
            ...developmentRoutes,
            { path: 'forbidden', element: <ForbiddenPage /> },
            { path: 'auth/login', element: <AuthPage /> },
            ...(mode === 'institutional'
              ? [
                  'auth/signup',
                  'auth/forgot-password',
                  'auth/reset-password',
                  'auth/action',
                  'auth/verify',
                  'auth/student-onboarding',
                  'auth/teacher-invite',
                  'auth/account',
                ].map((path) => ({
                  path,
                  element: path === 'auth/action' ? loadRoute(<EmailActionPage />) : <AuthPage />,
                }))
              : []),
            ...routeDefinitions.map((definition) => ({
              path: definition.path.slice(1),
              element: <RoleRoute definition={definition} />,
            })),
            { path: '*', element: loadRoute(<NotFoundPage />) },
          ],
        },
      ],
    },
  ];
}

export const appRoutes = createAppRoutes(appMode);
