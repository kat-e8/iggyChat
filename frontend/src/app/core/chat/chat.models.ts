// Which MCP servers a conversation is connected to -- switchable mid-session
// (see Chat.connect()). "ignition" is the default; "generic" and "all" are
// explicit widenings, and "canary" is a fully separate scope (the canary
// gateway has no API-key auth, so it's never folded into "all"). All chosen
// via the scope dropdown.
export type Scope = 'ignition' | 'generic' | 'all' | 'canary';

export type ToolCallStatus = 'in-progress' | 'done';

export type ToolCall = {
  id: string;
  name: string;
  status: ToolCallStatus;
};

export type ChatMessage = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  toolCalls: ToolCall[];
};

// Wire shapes sent by the Chat Bridge over /api/chat -- see
// chat-bridge/src/chat_bridge/claude_service.py's serialize_message /
// _serialize_block. "assistant" and "user" carry a typed content array;
// every other frame (ResultMessage, SystemMessage, ...) falls back to the
// Python dataclass's own field names, so only `type` is guaranteed there.
export type WireContentBlock = {
  type: string;
  text?: string;
  id?: string;
  name?: string;
  tool_use_id?: string;
  content?: WireContentBlock[];
};

export type WireMessage = {
  type: string;
  content?: WireContentBlock[];
  // Only present on "error" frames.
  message?: string;
  // Only present on a "session_scope" frame -- Chat-Bridge's confirmation of
  // the scope it actually applied (see app.py's websocket handler).
  scope?: Scope;
};
