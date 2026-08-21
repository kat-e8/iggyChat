import { Component, DestroyRef, ElementRef, afterRenderEffect, computed, inject, signal, viewChild } from '@angular/core';
import { NgOptimizedImage } from '@angular/common';
import { Router } from '@angular/router';
import { Auth } from '../../core/auth/auth';
import { Chat } from '../../core/chat/chat';
import { Scope } from '../../core/chat/chat.models';
import { ChatInput } from '../chat-input/chat-input';
import { ChatMessageList } from '../chat-message-list/chat-message-list';
import { ChatScopePicker } from '../chat-scope-picker/chat-scope-picker';
import { ChatStatus } from '../chat-status/chat-status';

const SCOPE_LABELS: Record<Scope, string> = {
  ignition: 'Ignition',
  generic: 'Generic',
  all: 'All',
};

@Component({
  selector: 'chat-page',
  imports: [ChatInput, ChatMessageList, ChatScopePicker, ChatStatus, NgOptimizedImage],
  templateUrl: './chat-page.html',
  styleUrl: './chat-page.scss',
})
export class ChatPage {
  protected readonly chat = inject(Chat);
  private readonly auth = inject(Auth);
  private readonly router = inject(Router);

  protected readonly sidebarCollapsed = signal(true);

  // No WebSocket is opened until the user picks a scope here -- Chat-Bridge
  // only accepts scope at connect time (see ChatSession's docstring), so this
  // is the only moment scope can be chosen. Shown again on "New Chat" instead
  // of Chat.reset() auto-reconnecting, since scope has to be re-chosen for
  // every new session, not carried over from the last one.
  protected readonly showScopePicker = signal(true);

  protected readonly hasMessages = computed(() => this.chat.messages().length > 0);
  protected readonly scopeLabel = computed(() => SCOPE_LABELS[this.chat.scope()]);

  protected readonly currentAssistantMessage = computed(() => {
    const last = this.chat.messages().at(-1);
    return last?.role === 'assistant' ? last : null;
  });

  private readonly transcript = viewChild<ElementRef<HTMLDivElement>>('transcript');

  constructor() {
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

  protected onScopeChosen(scope: Scope) {
    this.showScopePicker.set(false);
    void this.chat.connect(scope);
  }

  protected startNewChat() {
    this.chat.reset();
    this.showScopePicker.set(true);
  }

  protected async logout() {
    this.auth.logout();
    await this.router.navigateByUrl('/sign-in');
  }

  protected onSubmitPrompt(prompt: string) {
    void this.chat.send(prompt);
  }
}
