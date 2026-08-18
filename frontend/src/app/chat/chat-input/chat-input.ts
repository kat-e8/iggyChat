import { Component, input, output, signal } from '@angular/core';
import { FormField, FormRoot, form, required, submit } from '@angular/forms/signals';

@Component({
  selector: 'chat-input',
  imports: [FormField, FormRoot],
  templateUrl: './chat-input.html',
  styleUrl: './chat-input.scss',
})
export class ChatInput {
  readonly disabled = input.required<boolean>();
  readonly placeholder = input('Ask anything...');
  readonly submitPrompt = output<string>();

  private readonly draft = signal({ prompt: '' });

  protected readonly draftForm = form(this.draft, (path) => {
    required(path.prompt);
  });

  protected async onSubmit() {
    if (this.disabled()) {
      return;
    }
    await submit(this.draftForm, async (rootField) => {
      const { prompt } = rootField().value();
      this.submitPrompt.emit(prompt);
      // Reset through the FieldTree's own setter, not the raw backing
      // signal -- writes to the backing signal aren't reliably observed by
      // the [formField]-bound input, so the typed text would stay on
      // screen after submit (only masked when this component happens to
      // get destroyed/recreated right after, e.g. by an @if/@else switch).
      rootField().value.set({ prompt: '' });
      return undefined;
    });
  }
}
