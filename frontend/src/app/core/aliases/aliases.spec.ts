import { TestBed } from '@angular/core/testing';

import { Aliases } from './aliases';
import { Alias } from './aliases.models';

function mockResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

const IGN_STAGE: Alias = {
  name: 'ign-stage',
  system: 'ignition',
  url: 'https://ignition.stage.katlego.work',
  historian: null,
  is_default: true,
  created_by: 'me@example.com',
  created_at: 0,
};

describe('Aliases', () => {
  let service: Aliases;
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(Aliases);
    fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('load() fills aliases from /api/aliases', async () => {
    fetchSpy.mockResolvedValue(mockResponse(200, [IGN_STAGE]));

    await service.load();

    expect(fetchSpy).toHaveBeenCalledWith('/api/aliases', { credentials: 'include' });
    expect(service.aliases()).toEqual([IGN_STAGE]);
  });

  it('create() drops the historian for an Ignition alias, then reloads', async () => {
    fetchSpy.mockResolvedValueOnce(mockResponse(201, { name: 'ign-stage' }));
    fetchSpy.mockResolvedValueOnce(mockResponse(200, [IGN_STAGE]));

    await service.create({
      name: 'ign-stage',
      system: 'ignition',
      url: 'https://ignition.stage.katlego.work',
      api_key: 'key',
      historian: 'ignored',
    });

    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe('/api/aliases');
    expect(JSON.parse(init.body).historian).toBeNull();
    expect(service.aliases()).toEqual([IGN_STAGE]);
  });

  it('create() keeps a trimmed historian for a Canary alias', async () => {
    fetchSpy.mockResolvedValueOnce(mockResponse(201, { name: 'can-stage' }));
    fetchSpy.mockResolvedValueOnce(mockResponse(200, []));

    await service.create({
      name: 'can-stage',
      system: 'canary',
      url: 'https://canary-stage.stage.katlego.work',
      api_key: 'key',
      historian: '  histS ',
    });

    expect(JSON.parse(fetchSpy.mock.calls[0][1].body).historian).toBe('histS');
  });

  it('surfaces a 409 detail string as the error message', async () => {
    fetchSpy.mockResolvedValue(mockResponse(409, { detail: 'Alias already exists: ign-stage' }));

    await expect(service.remove('ign-stage')).rejects.toThrow('Alias already exists: ign-stage');
  });

  it('flattens a 422 validation detail list into one message', async () => {
    fetchSpy.mockResolvedValue(
      mockResponse(422, { detail: [{ loc: ['body', 'name'], msg: 'String should match pattern' }] }),
    );

    await expect(service.makeDefault('x')).rejects.toThrow('name: String should match pattern');
  });
});
