// Named connections (an Ignition gateway or a Canary Historian) that chat
// messages refer to by name -- "on ign-stage, what tags exist?". Shared by
// every user. See chat-bridge/src/chat_bridge/alias_store.py.
export type AliasSystem = 'ignition' | 'canary';

// What GET /api/aliases returns. Never includes the API key: keys are
// write-only over HTTP, sent once on create.
export type Alias = {
  name: string;
  system: AliasSystem;
  url: string;
  historian: string | null;
  is_default: boolean;
  created_by: string;
  created_at: number;
};

export type AliasDraft = {
  name: string;
  system: AliasSystem;
  url: string;
  api_key: string;
  // Canary only; blank means none.
  historian: string;
};
