import { Service, signal } from '@angular/core';
import { AuthCredentials, AuthErrorBody } from './auth.models';

@Service()
export class Auth {
  private readonly authenticatedState = signal(false);
  readonly isAuthenticated = this.authenticatedState.asReadonly();

  async login(credentials: AuthCredentials) {
    await this.authenticate('/api/auth/login', credentials);
  }

  // Clears local state only. The Chat Bridge issues the session as an
  // httpOnly cookie, which client-side code can't read or clear, and the
  // Bridge doesn't expose a logout endpoint yet -- so the cookie itself
  // stays valid server-side until it expires.
  logout() {
    this.authenticatedState.set(false);
  }

  // The Chat Bridge sets the session as an httpOnly cookie on success, so
  // the response body's access_token is redundant for the browser -- the
  // cookie is what actually authenticates the later /api/chat WebSocket.
  private async authenticate(url: string, credentials: AuthCredentials) {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as AuthErrorBody | null;
      throw new Error(body?.detail ?? 'Authentication failed');
    }

    this.authenticatedState.set(true);
  }
}
