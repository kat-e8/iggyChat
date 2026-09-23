import { Component, computed, inject, signal } from '@angular/core';
import { FormField, FormRoot, form, pattern, required, submit } from '@angular/forms/signals';
import { PasswordField } from '../../auth/password-field/password-field';
import { Aliases } from '../../core/aliases/aliases';
import { AliasDraft } from '../../core/aliases/aliases.models';

const EMPTY_DRAFT: AliasDraft = { name: '', system: 'ignition', url: '', api_key: '', historian: '' };

// Lists the shared aliases and adds new ones. Keys go straight to the Chat
// Bridge from here and are never shown again -- they never pass through the
// chat, so they never reach the model or the conversation history.
@Component({
  selector: 'alias-panel',
  imports: [FormField, FormRoot, PasswordField],
  templateUrl: './alias-panel.html',
  styleUrl: './alias-panel.scss',
})
export class AliasPanel {
  protected readonly store = inject(Aliases);

  protected readonly open = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);

  private readonly draft = signal<AliasDraft>({ ...EMPTY_DRAFT });

  // Same rules the Chat Bridge enforces (app.py's AliasCreate) -- checked
  // here first so a typo is caught before a round trip.
  protected readonly aliasForm = form(this.draft, (path) => {
    required(path.name, { message: 'Name is required' });
    pattern(path.name, /^[a-z0-9][a-z0-9-]{0,62}$/, {
      message: 'Lowercase letters, digits and dashes, e.g. ign-stage',
    });
    required(path.url, { message: 'URL is required' });
    pattern(path.url, /^https?:\/\/\S+$/, { message: 'Must start with http:// or https://' });
    required(path.api_key, { message: 'API key is required' });
  });

  protected readonly isCanary = computed(() => this.aliasForm.system().value() === 'canary');

  protected async toggle() {
    this.open.update((isOpen) => !isOpen);
    if (this.open()) {
      await this.run(() => this.store.load());
    }
  }

  protected async onSubmit() {
    let added: string | null = null;
    await submit(this.aliasForm, async (rootField) => {
      const draft = rootField().value();
      if (await this.run(() => this.store.create(draft))) {
        added = draft.name;
      }
      return undefined;
    });
    if (added) {
      // reset() clears touched/dirty as well as the values -- clearing only
      // the values left every field "touched" and empty, so a successful
      // add immediately showed "Name is required" etc. and looked like it
      // had failed. Done after submit() settles, since submit() itself
      // marks every field touched.
      this.aliasForm().reset({ ...EMPTY_DRAFT });
      this.notice.set(`Added ${added}. Name it in a message, e.g. "on ${added}, what tags exist?"`);
    }
  }

  protected remove(name: string) {
    void this.run(() => this.store.remove(name));
  }

  protected makeDefault(name: string) {
    void this.run(() => this.store.makeDefault(name));
  }

  private async run(action: () => Promise<void>): Promise<boolean> {
    this.error.set(null);
    this.notice.set(null);
    try {
      await action();
      return true;
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Something went wrong');
      return false;
    }
  }
}
