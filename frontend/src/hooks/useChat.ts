import { useCallback, useRef, useState } from "react";
import { streamChat } from "../api/chat";
import type { Message } from "../api/types";

export interface ChatMessage extends Message {
  id: string;
}

interface ChatState {
  messages: ChatMessage[];
  conversationId: string | undefined;
  streaming: boolean;
  error: string | null;
}

export function useChat(token: string) {
  const [state, setState] = useState<ChatState>({
    messages: [],
    conversationId: undefined,
    streaming: false,
    error: null,
  });
  const abortRef = useRef<(() => void) | null>(null);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || state.streaming) return;

      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: content.trim(),
      };
      const assistantMsgId = crypto.randomUUID();

      setState((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          userMsg,
          { id: assistantMsgId, role: "assistant", content: "" },
        ],
        streaming: true,
        error: null,
      }));

      let cancelled = false;
      abortRef.current = () => {
        cancelled = true;
      };

      try {
        const history: Message[] = [
          ...state.messages.map(({ role, content }) => ({ role, content })),
          { role: "user", content: content.trim() },
        ];

        let conversationId = state.conversationId;

        for await (const chunk of streamChat(token, history, conversationId)) {
          if (cancelled) break;

          if (chunk.conversation_id && !conversationId) {
            conversationId = chunk.conversation_id;
          }

          if (chunk.delta) {
            setState((prev) => ({
              ...prev,
              conversationId: conversationId ?? prev.conversationId,
              messages: prev.messages.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: m.content + chunk.delta }
                  : m,
              ),
            }));
          }
        }
      } catch (e) {
        if (!cancelled) {
          setState((prev) => ({
            ...prev,
            error: e instanceof Error ? e.message : "Unknown error",
            messages: prev.messages.filter((m) => m.id !== assistantMsgId),
          }));
        }
      } finally {
        setState((prev) => ({ ...prev, streaming: false }));
        abortRef.current = null;
      }
    },
    [token, state.messages, state.streaming, state.conversationId],
  );

  const stopStreaming = useCallback(() => {
    abortRef.current?.();
  }, []);

  const clearChat = useCallback(() => {
    setState({ messages: [], conversationId: undefined, streaming: false, error: null });
  }, []);

  return { ...state, sendMessage, stopStreaming, clearChat };
}
