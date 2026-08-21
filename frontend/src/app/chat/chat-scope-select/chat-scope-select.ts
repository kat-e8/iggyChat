import { Component, input, output } from '@angular/core';
import { Scope } from '../../core/chat/chat.models';

type ScopeOption = { value: Scope; label: string };

// Ignition is the implicit default; Generic and All are explicit widenings.
// Same three options whether picked before the first message or mid-session.
const OPTIONS: ScopeOption[] = [
  { value: 'ignition', label: 'Ignition' },
  { value: 'generic', label: 'Generic' },
  { value: 'all', label: 'All' },
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
