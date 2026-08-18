import { Component, computed, input } from '@angular/core';
import { NgOptimizedImage } from '@angular/common';
import { ChatMessage } from '../../core/chat/chat.models';

@Component({
  selector: 'chat-message-list',
  imports: [NgOptimizedImage],
  templateUrl: './chat-message-list.html',
  styleUrl: './chat-message-list.scss',
})
export class ChatMessageList {
  readonly messages = input.required<ChatMessage[]>();

  protected readonly renderableMessages = computed(() =>
    this.messages().filter((message) => message.text.length > 0 || message.toolCalls.length > 0),
  );
}
