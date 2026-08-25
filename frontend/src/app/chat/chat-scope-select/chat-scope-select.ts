import { Component, input, output } from '@angular/core';
import { Scope } from '../../core/chat/chat.models';

type ScopeOption = { value: Scope; label: string };

// Ignition is the implicit default; Generic and All are explicit widenings.
// Canary, Training, and Tickets are fully separate scopes (Canary and
// Tickets: unauthenticated gateway; Training and Tickets: unrelated domain)
// -- none is part of "all". Same options whether picked before the first
// message or mid-session.
const OPTIONS: ScopeOption[] = [
  { value: 'ignition', label: 'Ignition' },
  { value: 'generic', label: 'Generic' },
  { value: 'all', label: 'All' },
  { value: 'canary', label: 'Canary' },
  { value: 'trainer', label: 'Training' },
  { value: 'tickets', label: 'Tickets' },
];

@Component({
  selector: 'chat-scope-select',
  templateUrl: './chat-scope-select.html',
  styleUrl: './chat-scope-select.scss',
})
export class ChatScopeSelect {
  readonly scope = input.required<Scope>();
  readonly scopeChosen = output<Scope>();

  protected readonly options = OPTIONS;

  protected onChange(event: Event) {
    const value = (event.target as HTMLSelectElement).value as Scope;
    this.scopeChosen.emit(value);
  }
}
