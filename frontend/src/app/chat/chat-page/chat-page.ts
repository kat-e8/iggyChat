import { Component, DestroyRef, ElementRef, afterRenderEffect, computed, inject, signal, viewChild } from '@angular/core';
import { NgOptimizedImage } from '@angular/common';
import { Router } from '@angular/router';
import { Auth } from '../../core/auth/auth';
import { Chat } from '../../core/chat/chat';
import { Scope } from '../../core/chat/chat.models';
import { ChatInput } from '../chat-input/chat-input';
import { ChatMessageList } from '../chat-message-list/chat-message-list';
import { ChatScopeSelect } from '../chat-scope-select/chat-scope-select';
import { ChatStatus } from '../chat-status/chat-status';

@Component({
  selector: 'chat-page',
  imports: [ChatInput, ChatMessageList, ChatScopeSelect, ChatStatus, NgOptimizedImage],
  templateUrl: './chat-page.html',
  styleUrl: './chat-page.scss',
})
export class ChatPage {
  protected readonly chat = inject(Chat);
  private readonly auth = inject(Auth);
  private readonly router = inject(Router);

  protected readonly sidebarCollapsed = signal(true);

  protected readonly hasMessages = computed(() => this.chat.messages().length > 0);

  protected readonly currentAssistantMessage = computed(() => {
    const last = this.chat.messages().at(-1);
    return last?.role === 'assistant' ? last : null;
  });

  private readonly transcript = viewChild<ElementRef<HTMLDivElement>>('transcript');

  constructor() {
    void this.chat.connect();
    inject(DestroyRef).onDestroy(() => this.chat.disconnect());

    // Re-runs after every DOM update triggered by new messages/streamed
    // tokens (scrollHeight isn't reliable until the new content has
    // actually been rendered) and keeps the transcript pinned to the
    // latest message.
    afterRenderEffect(() => {
      this.chat.messages();
      this.chat.awaitingReply();
      const el = this.transcript()?.nativeElement;
      if (el) {
        el.scrollTop = el.scrollHeight;
      }
    });
  }

  protected toggleSidebar() {
    this.sidebarCollapsed.update((collapsed) => !collapsed);
  }

  // Same handler whether the dropdown is touched before the first message
  // (Chat.changeScope defers to connect()) or mid-conversation (swaps scope
  // on the open connection, conversation history intact) -- see Chat.changeScope.
  protected onScopeChosen(scope: Scope) {
    this.chat.changeScope(scope);
  }

  protected startNewChat() {
    const scope = this.chat.scope();
    this.chat.reset();
    void this.chat.connect(scope);
  }

  protected async logout() {
    this.auth.logout();
    await this.router.navigateByUrl('/sign-in');
  }

  protected onSubmitPrompt(prompt: string) {
    void this.chat.send(prompt);
  }
}
