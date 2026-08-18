import { Routes } from '@angular/router';

// Signup is closed -- accounts are provisioned by the operator via
// manage_users.py, not through the app -- so there is no sign-up route.
export const authRoutes: Routes = [
  {
    path: 'sign-in',
    loadComponent: () => import('./sign-in/sign-in').then((m) => m.SignIn),
  },
];
