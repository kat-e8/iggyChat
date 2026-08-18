import { TestBed } from '@angular/core/testing';
import { CanActivateFn, Router, UrlTree, provideRouter } from '@angular/router';

import { authGuard } from './auth-guard';
import { Auth } from './auth';

describe('authGuard', () => {
  const executeGuard: CanActivateFn = (...guardParameters) =>
    TestBed.runInInjectionContext(() => authGuard(...guardParameters));

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideRouter([])] });
  });

  it('allows navigation when the session is authenticated', () => {
    const auth = TestBed.inject(Auth);
    vi.spyOn(auth, 'isAuthenticated').mockReturnValue(true);

    const result = executeGuard({} as never, {} as never);

    expect(result).toBe(true);
  });

  it('redirects to /sign-in when the session is not authenticated', () => {
    const result = executeGuard({} as never, {} as never);

    expect(result).not.toBe(true);
    const router = TestBed.inject(Router);
    expect((result as UrlTree).toString()).toBe(router.createUrlTree(['/sign-in']).toString());
  });
});
