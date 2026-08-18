import { TestBed } from '@angular/core/testing';

import { Auth } from './auth';

function mockResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

describe('Auth', () => {
  let service: Auth;
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(Auth);
    fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('starts unauthenticated', () => {
    expect(service.isAuthenticated()).toBe(false);
  });

  it('login() posts credentials to /api/auth/login and marks the session authenticated', async () => {
    fetchSpy.mockResolvedValue(
      mockResponse(200, { access_token: 'token', token_type: 'bearer' }),
    );

    await service.login({ email: 'test@angular-university.io', password: 'Angular123' });

    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/auth/login',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({ email: 'test@angular-university.io', password: 'Angular123' }),
      }),
    );
    expect(service.isAuthenticated()).toBe(true);
  });

  it('login() surfaces the server error message and leaves the session unauthenticated', async () => {
    fetchSpy.mockResolvedValue(mockResponse(401, { detail: 'Invalid email or password' }));

    await expect(
      service.login({ email: 'test@angular-university.io', password: 'wrong' }),
    ).rejects.toThrow('Invalid email or password');
    expect(service.isAuthenticated()).toBe(false);
  });

  it('signup() posts credentials to /api/auth/signup and marks the session authenticated', async () => {
    fetchSpy.mockResolvedValue(
      mockResponse(201, { access_token: 'token', token_type: 'bearer' }),
    );

    await service.signup({ email: 'new@example.com', password: 'hunter2pass' });

    expect(fetchSpy).toHaveBeenCalledWith('/api/auth/signup', expect.objectContaining({ method: 'POST' }));
    expect(service.isAuthenticated()).toBe(true);
  });

  it('logout() clears the local session state', async () => {
    fetchSpy.mockResolvedValue(mockResponse(200, { access_token: 'token', token_type: 'bearer' }));
    await service.login({ email: 'test@angular-university.io', password: 'Angular123' });

    service.logout();

    expect(service.isAuthenticated()).toBe(false);
  });
});
