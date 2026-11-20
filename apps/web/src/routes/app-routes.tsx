import type { RouteObject } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import { appMode } from '../config/runtime-config';
import { AuthPage } from '../pages/AuthPage';
import { DesignSystemPage } from '../pages/DesignSystemPage';
import { DevelopmentRolePreviewPage } from '../pages/DevelopmentRolePreviewPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { ForbiddenPage, RoleProviderLayout, RoleRoute } from './RouteGuard';
import { routeDefinitions } from './route-config';

export const appRoutes: RouteObject[] = [
  {
    element: <RoleProviderLayout />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <AuthPage /> },
          { path: 'dev/design-system', element: <DesignSystemPage /> },
          { path: 'dev/role-preview', element: <DevelopmentRolePreviewPage /> },
          { path: 'forbidden', element: <ForbiddenPage /> },
          { path: 'auth/login', element: <AuthPage /> },
          ...(appMode === 'institutional'
            ? [
                'auth/signup',
                'auth/forgot-password',
                'auth/reset-password',
                'auth/verify',
                'auth/student-onboarding',
                'auth/teacher-invite',
                'auth/account',
              ].map((path) => ({
                path,
                element: <AuthPage />,
              }))
            : []),
          ...routeDefinitions.map((definition) => ({
            path: definition.path.slice(1),
            element: <RoleRoute definition={definition} />,
          })),
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
];
