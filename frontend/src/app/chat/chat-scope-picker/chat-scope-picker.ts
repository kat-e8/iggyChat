import { Component, output, signal } from '@angular/core';
import { Scope } from '../../core/chat/chat.models';

type ScopeOption = { value: Scope; label: string; description: string };

// Ignition is the implicit default (pre-selected, no action needed to keep
// it); Generic and All are the explicit widenings a user opts into per the
// scoped-gateway rollout plan.
const OPTIONS: ScopeOption[] = [
  { value: 'ignition', label: 'Ignition', description: 'Tags and SCADA data only' },
  { value: 'generic', label: 'Generic', description: 'Docker, git, Postgres, coder commands' },
  { value: 'all', label: 'All', description: 'Everything above' },
];

@Component({
  selector: 'chat-scope-picker',
  templateUrl: './chat-scope-picker.html',
  styleUrl: './chat-scope-picker.scss',
})
export class ChatScopePicker {
  // Emitted once, when the user confirms -- this is the only way a scope
  // choice leaves this component. There is deliberately no way to change it
  // afterwards short of a new conversation (see chat-page.ts).
  readonly scopeChosen = output<Scope>();

  protected readonly options = OPTIONS;
  protected readonly selected = signal<Scope>('ignition');

  protected select(value: Scope) {
    this.selected.set(value);
  }

  protected confirm() {
    this.scopeChosen.emit(this.selected());
  }
}
