export interface Message {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatChunk {
  delta: string;
  done: boolean;
  conversation_id?: string;
}
