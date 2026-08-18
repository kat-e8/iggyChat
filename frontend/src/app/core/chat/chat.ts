import { Service, signal } from '@angular/core';
import { ChatMessage, ToolCall, WireMessage } from './chat.models';

@Service()
export class Chat {
  private socket: WebSocket | null = null;
  private currentAssistantId: string | null = null;
  private nextId = 0;

  readonly messages = signal<ChatMessage[]>([]);
  readonly connected = signal(false);
  readonly awaitingReply = signal(false);
  readonly connectionError = signal<string | null>(null);

  connect() {
    if (this.socket) {
      return Promise.resolve();
    }

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${protocol}//${location.host}/api/chat`);
    this.socket = socket;

    return new Promise<void>((resolve, reject) => {
      socket.addEventListener('open', () => {
        this.connected.set(true);
        this.connectionError.set(null);
        resolve();
      });
      socket.addEventListener('message', (event) => this.handleFrame(JSON.parse(event.data)));
      socket.addEventListener('close', () => {
        this.connected.set(false);
        this.socket = null;
        // A turn was in flight when the connection dropped -- stop the
        // "waiting for reply" spinner instead of leaving it spinning forever.
        if (this.awaitingReply()) {
          this.awaitingReply.set(false);
          this.connectionError.set('Connection to the chat service was lost.');
        }
      });
      socket.addEventListener('error', () => {
        const error = new Error('Chat connection failed');
        this.connectionError.set('Could not reach the chat service. Check your connection and try again.');
        reject(error);
      });
    });
  }

  disconnect() {
    this.socket?.close();
    this.socket = null;
    this.connected.set(false);
  }

  // Clears the transcript and opens a fresh connection -- the Chat Bridge
  // holds conversation state per WebSocket connection (one ClaudeSDKClient
  // per connection), so a new chat needs a new socket, not just a cleared list.
  reset() {
    // Clear awaitingReply first so the close handler doesn't mistake this
    // deliberate reset for a dropped connection mid-turn.
    this.awaitingReply.set(false);
    this.disconnect();
    this.messages.set([]);
    this.connectionError.set(null);
    this.currentAssistantId = null;
    void this.connect();
  }

  async send(prompt: string) {
    const trimmed = prompt.trim();
    if (!trimmed) {
      return;
    }
    this.connectionError.set(null);
    if (!this.connected()) {
      try {
        await this.connect();
      } catch {
        // connectionError is already set by connect()'s own error handler.
        return;
      }
    }

    const userId = this.generateId();
    const assistantId = this.generateId();
    this.currentAssistantId = assistantId;

    this.messages.update((current) => [
      ...current,
      { id: userId, role: 'user', text: trimmed, toolCalls: [] },
      { id: assistantId, role: 'assistant', text: '', toolCalls: [] },
    ]);
    this.awaitingReply.set(true);

    this.socket?.send(JSON.stringify({ content: trimmed }));
  }

  private generateId() {
    this.nextId += 1;
    return `msg-${this.nextId}`;
  }

  private handleFrame(message: WireMessage) {
    if (message.type === 'assistant' || message.type === 'user') {
      this.applyContentBlocks(message.content ?? []);
      return;
    }
    if (message.type === 'ResultMessage') {
      this.awaitingReply.set(false);
      this.currentAssistantId = null;
    }
    // Other frame types (SystemMessage, StreamEvent, ...) aren't rendered yet.
  }

  private applyContentBlocks(blocks: WireMessage['content']) {
    for (const block of blocks ?? []) {
      if (block.type === 'text' && block.text) {
        this.appendAssistantText(block.text);
      } else if (block.type === 'tool_use' && block.id && block.name) {
        this.addToolCall({ id: block.id, name: block.name, status: 'in-progress' });
      } else if (block.type === 'tool_result' && block.tool_use_id) {
        this.completeToolCall(block.tool_use_id);
      }
    }
  }

  private appendAssistantText(text: string) {
    this.updateCurrentAssistantMessage((message) => ({ ...message, text: message.text + text }));
  }

  private addToolCall(toolCall: ToolCall) {
    this.updateCurrentAssistantMessage((message) => ({
      ...message,
      toolCalls: [...message.toolCalls, toolCall],
    }));
  }

  private completeToolCall(toolUseId: string) {
    this.updateCurrentAssistantMessage((message) => ({
      ...message,
      toolCalls: message.toolCalls.map((toolCall) =>
        toolCall.id === toolUseId ? { ...toolCall, status: 'done' } : toolCall,
      ),
    }));
  }

  private updateCurrentAssistantMessage(updater: (message: ChatMessage) => ChatMessage) {
    const targetId = this.currentAssistantId;
    if (!targetId) {
      return;
    }
    this.messages.update((current) =>
      current.map((message) => (message.id === targetId ? updater(message) : message)),
    );
  }
}
