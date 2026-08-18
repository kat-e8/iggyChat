import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: '/home', pathMatch: 'full' },
  // /chat is the only screen once signed in -- /home is a stable, friendly
  // entry point that always resolves there; the chat route's authGuard is
  // what actually decides whether that succeeds or bounces to /sign-in.
  { path: 'home', redirectTo: '/chat', pathMatch: 'full' },
  {
    path: '',
    loadChildren: () => import('./auth/auth.routes').then((m) => m.authRoutes),
  },
  {
    path: '',
    loadChildren: () => import('./chat/chat.routes').then((m) => m.chatRoutes),
  },
];
