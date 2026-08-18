import { Component, computed, effect, input, signal } from '@angular/core';
import { NgOptimizedImage } from '@angular/common';
import { ChatMessage } from '../../core/chat/chat.models';

@Component({
  selector: 'chat-status',
  imports: [NgOptimizedImage],
  templateUrl: './chat-status.html',
  styleUrl: './chat-status.scss',
})
export class ChatStatus {
  readonly awaiting = input.required<boolean>();
  readonly currentMessage = input<ChatMessage | null>(null);

  protected readonly activeToolCall = computed(
    () => this.currentMessage()?.toolCalls.find((toolCall) => toolCall.status === 'in-progress') ?? null,
  );

  protected readonly elapsedSeconds = signal(0);

  constructor() {
    effect((onCleanup) => {
      if (!this.awaiting()) {
        this.elapsedSeconds.set(0);
        return;
      }
      const intervalId = setInterval(() => this.elapsedSeconds.update((seconds) => seconds + 1), 1000);
      onCleanup(() => clearInterval(intervalId));
    });
  }
}
