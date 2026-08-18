import { Component, computed, input, model, output, signal } from '@angular/core';
import { FormValueControl } from '@angular/forms/signals';

@Component({
  selector: 'password-field',
  imports: [],
  templateUrl: './password-field.html',
  styleUrl: './password-field.scss',
})
export class PasswordField implements FormValueControl<string> {
  readonly value = model.required<string>();
  readonly fieldId = input.required<string>();
  readonly label = input.required<string>();
  readonly placeholder = input('');
  readonly autocomplete = input<'current-password' | 'new-password'>('current-password');
  readonly invalid = input(false);
  readonly touched = input(false);
  // FormField only learns a custom control was interacted with via this
  // output -- it can't observe an arbitrary internal DOM structure itself.
  readonly touch = output<void>();

  protected readonly visible = signal(false);
  protected readonly inputType = computed(() => (this.visible() ? 'text' : 'password'));
  protected readonly toggleLabel = computed(() => (this.visible() ? 'Hide password' : 'Show password'));
  // Only surface the invalid style once the user has interacted with the
  // field -- FormField feeds `invalid` from the field's error state as soon
  // as a `required` validator sees an empty value, before any interaction.
  protected readonly showInvalid = computed(() => this.invalid() && this.touched());

  protected toggleVisible() {
    this.visible.update((currentlyVisible) => !currentlyVisible);
  }
}
