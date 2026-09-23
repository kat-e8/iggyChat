import { Service, signal } from '@angular/core';
import { Alias, AliasDraft } from './aliases.models';

type ErrorBody = { detail?: string | { msg: string; loc: (string | number)[] }[] };

// Thin wrapper over the Chat Bridge's /api/aliases. Same fetch + httpOnly
// cookie approach as Auth -- the session cookie authenticates every call.
@Service()
export class Aliases {
  private readonly state = signal<Alias[]>([]);
  readonly aliases = this.state.asReadonly();

  async load() {
    const response = await fetch('/api/aliases', { credentials: 'include' });
    await this.throwIfFailed(response);
    this.state.set((await response.json()) as Alias[]);
  }

  async create(draft: AliasDraft) {
    const response = await fetch('/api/aliases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        ...draft,
        historian: draft.system === 'canary' && draft.historian.trim() ? draft.historian.trim() : null,
      }),
    });
    await this.throwIfFailed(response);
    await this.load();
  }

  async remove(name: string) {
    const response = await fetch(`/api/aliases/${encodeURIComponent(name)}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    await this.throwIfFailed(response);
    await this.load();
  }

  async makeDefault(name: string) {
    const response = await fetch(`/api/aliases/${encodeURIComponent(name)}/default`, {
      method: 'PUT',
      credentials: 'include',
    });
    await this.throwIfFailed(response);
    await this.load();
  }

  // FastAPI sends `detail` as a string for HTTPExceptions and as a list of
  // {loc, msg} for request validation (422) -- surface either as one line.
  private async throwIfFailed(response: Response) {
    if (response.ok) {
      return;
    }
    const body = (await response.json().catch(() => null)) as ErrorBody | null;
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((d) => `${d.loc.at(-1)}: ${d.msg}`).join('; ')
      : (detail ?? `Request failed (${response.status})`);
    throw new Error(message);
  }
}
