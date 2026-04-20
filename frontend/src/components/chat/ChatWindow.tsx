import { useChat } from "../../hooks/useChat";
import { MessageInput } from "./MessageInput";
import { MessageList } from "./MessageList";

interface Props {
  token: string;
}

export function ChatWindow({ token }: Props) {
  const { messages, streaming, error, sendMessage, stopStreaming, clearChat } =
    useChat(token);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-2">
        <span className="text-xs text-gray-500">Chat</span>
        {messages.length > 0 && (
          <button
            onClick={clearChat}
            className="text-xs text-gray-600 hover:text-gray-400"
          >
            Clear
          </button>
        )}
      </div>

      {error && (
        <div className="mx-4 mt-3 rounded-lg border border-red-800 bg-red-950 px-3 py-2 text-xs text-red-400">
          {error}
        </div>
      )}

      <MessageList messages={messages} streaming={streaming} />
      <MessageInput
        onSend={sendMessage}
        onStop={stopStreaming}
        disabled={false}
        streaming={streaming}
      />
    </div>
  );
}
