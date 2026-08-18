import { Routes } from '@angular/router';
import { authGuard } from '../core/auth/auth-guard';

export const chatRoutes: Routes = [
  {
    path: 'chat',
    canActivate: [authGuard],
    loadComponent: () => import('./chat-page/chat-page').then((m) => m.ChatPage),
  },
];
