import { APPLICATION_RID, FOUNDRY_URL } from "../foundry";
import type { ChatChunk, Message } from "./types";

// Foundry CM function invocation endpoint.
// The CM `chat` function is exposed under the third-party application's API path.
// Adjust this if Foundry routes CM functions differently in your deployment.
const CM_CHAT_URL = `${FOUNDRY_URL}/api/v2/thirdPartyApplications/${APPLICATION_RID}/computeModules/functions/chat`;

export async function* streamChat(
  token: string,
  messages: Message[],
  conversationId?: string,
): AsyncGenerator<ChatChunk> {
  const response = await fetch(CM_CHAT_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      event: {
        messages,
        conversation_id: conversationId ?? null,
        model: null,
        max_tokens: 4096,
      },
    }),
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`CM chat failed: HTTP ${response.status} — ${body.slice(0, 200)}`);
  }

  if (!response.body) throw new Error("No response body");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        // Handle both raw SSE ("data: {...}") and bare JSON chunks
        const raw = trimmed.startsWith("data: ") ? trimmed.slice(6) : trimmed;
        if (raw === "[DONE]") return;

        try {
          const chunk = JSON.parse(raw) as ChatChunk;
          yield chunk;
          if (chunk.done) return;
        } catch {
          // non-JSON line (e.g. SSE "event:" line) — skip
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
