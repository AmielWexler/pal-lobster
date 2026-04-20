import { useEffect, useRef } from "react";
import type { ChatMessage } from "../../hooks/useChat";

interface Props {
  messages: ChatMessage[];
  streaming: boolean;
}

export function MessageList({ messages, streaming }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-gray-600">
        Start a conversation
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
        >
          <div
            className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
              msg.role === "user"
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-100"
            }`}
          >
            {msg.content || (
              <span className="inline-block h-4 w-1 animate-pulse bg-gray-400" />
            )}
          </div>
        </div>
      ))}
      {streaming && messages.at(-1)?.role === "assistant" && !messages.at(-1)?.content && (
        <div className="flex justify-start">
          <div className="flex gap-1 rounded-2xl bg-gray-800 px-4 py-3">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="h-1.5 w-1.5 animate-bounce rounded-full bg-gray-400"
                style={{ animationDelay: `${i * 150}ms` }}
              />
            ))}
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
