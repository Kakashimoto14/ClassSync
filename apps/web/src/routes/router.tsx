import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from '../layouts/AppLayout';
import { AuthPage } from '../pages/AuthPage';
import { DesignSystemPage } from '../pages/DesignSystemPage';
import { DevelopmentRolePreviewPage } from '../pages/DevelopmentRolePreviewPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { ForbiddenPage, RoleProviderLayout, RoleRoute } from './RouteGuard';
import { routeDefinitions } from './route-config';

export const router = createBrowserRouter([
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
          ...routeDefinitions.map(definition => ({
            path: definition.path.slice(1),
            element: <RoleRoute definition={definition} />,
          })),
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
]);
