import { TestBed } from '@angular/core/testing';

import { Chat } from './chat';

type Listener = (event: unknown) => void;

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  readonly sent: string[] = [];
  private readonly listeners = new Map<string, Listener[]>();

  constructor(readonly url: string) {
    MockWebSocket.instances.push(this);
  }

  addEventListener(type: string, listener: Listener) {
    const forType = this.listeners.get(type) ?? [];
    forType.push(listener);
    this.listeners.set(type, forType);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.dispatch('close', {});
  }

  dispatch(type: string, event: unknown) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }

  dispatchMessage(payload: unknown) {
    this.dispatch('message', { data: JSON.stringify(payload) });
  }
}

describe('Chat', () => {
  let service: Chat;

  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
    TestBed.configureTestingModule({});
    service = TestBed.inject(Chat);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('connect() opens a socket at /api/chat and resolves once it opens', async () => {
    const connectPromise = service.connect();
    const socket = MockWebSocket.instances[0];
    expect(socket.url).toContain('/api/chat');

    socket.dispatch('open', {});
    await connectPromise;

    expect(service.connected()).toBe(true);
  });

  it('connect() defaults to ignition scope and sets it immediately', () => {
    void service.connect();
    const socket = MockWebSocket.instances[0];

    expect(socket.url).toContain('scope=ignition');
    expect(service.scope()).toBe('ignition');
  });

  it('connect(scope) puts the requested scope on the WebSocket URL', () => {
    void service.connect('generic');
    const socket = MockWebSocket.instances[0];

    expect(socket.url).toContain('scope=generic');
    expect(service.scope()).toBe('generic');
  });

  it('a "session_scope" frame corrects scope to whatever Chat-Bridge actually applied', async () => {
    const connectPromise = service.connect('generic');
    const socket = MockWebSocket.instances[0];
    socket.dispatch('open', {});
    await connectPromise;

    socket.dispatchMessage({ type: 'session_scope', scope: 'ignition' });

    expect(service.scope()).toBe('ignition');
  });

  it('changeScope() before any connection just connects with that scope', () => {
    service.changeScope('generic');
    const socket = MockWebSocket.instances[0];

    expect(socket.url).toContain('scope=generic');
  });

  it('changeScope() while connected sends a change_scope message and waits for confirmation', async () => {
    const connectPromise = service.connect('ignition');
    const socket = MockWebSocket.instances[0];
    socket.dispatch('open', {});
    await connectPromise;

    service.changeScope('generic');

    expect(socket.sent).toContain(JSON.stringify({ action: 'change_scope', scope: 'generic' }));
    // Not applied optimistically -- still the pre-switch value until confirmed.
    expect(service.scope()).toBe('ignition');
    // No second socket opened -- the existing connection is reused.
    expect(MockWebSocket.instances.length).toBe(1);

    socket.dispatchMessage({ type: 'session_scope', scope: 'generic' });
    expect(service.scope()).toBe('generic');
  });

  it('send() appends a user message and a placeholder assistant message, then sends the prompt', async () => {
    const connectPromise = service.connect();
    MockWebSocket.instances[0].dispatch('open', {});
    await connectPromise;

    await service.send('Hello there');

    const messages = service.messages();
    expect(messages).toEqual([
      { id: 'msg-1', role: 'user', text: 'Hello there', toolCalls: [] },
      { id: 'msg-2', role: 'assistant', text: '', toolCalls: [] },
    ]);
    expect(service.awaitingReply()).toBe(true);
    expect(MockWebSocket.instances[0].sent).toEqual([JSON.stringify({ content: 'Hello there' })]);
  });

  it('streams assistant text and resolves tool calls from incoming frames', async () => {
    const connectPromise = service.connect();
    const socket = MockWebSocket.instances[0];
    socket.dispatch('open', {});
    await connectPromise;

    await service.send('Read the Village tag');

    socket.dispatchMessage({
      type: 'assistant',
      content: [{ type: 'text', text: 'Checking the tag now.' }],
    });
    socket.dispatchMessage({
      type: 'assistant',
      content: [{ type: 'tool_use', id: 'tool-1', name: 'mcp__ignition__read_tags', input: {} }],
    });

    let assistantMessage = service.messages().at(-1)!;
    expect(assistantMessage.text).toBe('Checking the tag now.');
    expect(assistantMessage.toolCalls).toEqual([
      { id: 'tool-1', name: 'mcp__ignition__read_tags', status: 'in-progress' },
    ]);

    socket.dispatchMessage({
      type: 'user',
      content: [{ type: 'tool_result', tool_use_id: 'tool-1', content: [] }],
    });
    socket.dispatchMessage({
      type: 'assistant',
      content: [{ type: 'text', text: ' Value is 45.6.' }],
    });

    assistantMessage = service.messages().at(-1)!;
    expect(assistantMessage.text).toBe('Checking the tag now. Value is 45.6.');
    expect(assistantMessage.toolCalls).toEqual([
      { id: 'tool-1', name: 'mcp__ignition__read_tags', status: 'done' },
    ]);

    socket.dispatchMessage({ type: 'ResultMessage', result: 'ok', terminal_reason: 'success' });
    expect(service.awaitingReply()).toBe(false);
  });

  it('reset() clears the transcript and disconnects without reconnecting', async () => {
    const connectPromise = service.connect();
    MockWebSocket.instances[0].dispatch('open', {});
    await connectPromise;
    await service.send('Hello');

    service.reset();

    expect(service.messages()).toEqual([]);
    expect(service.connected()).toBe(false);
    // No new socket opened -- scope for the next session is chosen by the
    // caller (ChatPage's scope picker), not decided here.
    expect(MockWebSocket.instances.length).toBe(1);
  });

  it('send() surfaces a connectionError and adds no messages when the connection fails', async () => {
    const sendPromise = service.send('hi');
    MockWebSocket.instances[0].dispatch('error', {});
    await sendPromise;

    expect(service.messages()).toEqual([]);
    expect(service.connectionError()).toBeTruthy();
  });

  it('clears awaitingReply and sets connectionError if the socket drops mid-turn', async () => {
    const connectPromise = service.connect();
    const socket = MockWebSocket.instances[0];
    socket.dispatch('open', {});
    await connectPromise;
    await service.send('Hello');
    expect(service.awaitingReply()).toBe(true);

    socket.dispatch('close', {});

    expect(service.awaitingReply()).toBe(false);
    expect(service.connectionError()).toBeTruthy();
  });

  it('reset() does not report connectionError even if a reply was pending', async () => {
    const connectPromise = service.connect();
    const socket = MockWebSocket.instances[0];
    socket.dispatch('open', {});
    await connectPromise;
    await service.send('Hello');
    expect(service.awaitingReply()).toBe(true);

    service.reset();

    expect(service.connectionError()).toBeNull();
  });
});
