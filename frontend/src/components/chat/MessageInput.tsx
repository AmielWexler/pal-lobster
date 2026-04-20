import { type KeyboardEvent, useRef, useState } from "react";

interface Props {
  onSend: (message: string) => void;
  onStop: () => void;
  disabled: boolean;
  streaming: boolean;
}

export function MessageInput({ onSend, onStop, disabled, streaming }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  };

  return (
    <div className="border-t border-gray-800 px-4 py-3">
      <div className="flex items-end gap-2 rounded-xl border border-gray-700 bg-gray-900 px-3 py-2 focus-within:border-gray-500">
        <textarea
          ref={textareaRef}
          className="flex-1 resize-none bg-transparent text-sm text-gray-100 placeholder-gray-600 outline-none"
          placeholder="Message Lobster… (Shift+Enter for newline)"
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          disabled={disabled && !streaming}
        />
        {streaming ? (
          <button
            onClick={onStop}
            className="rounded-lg bg-gray-700 p-1.5 text-gray-300 hover:bg-gray-600"
            title="Stop"
          >
            <StopIcon />
          </button>
        ) : (
          <button
            onClick={submit}
            disabled={!value.trim() || disabled}
            className="rounded-lg bg-blue-600 p-1.5 text-white hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed"
            title="Send"
          >
            <SendIcon />
          </button>
        )}
      </div>
    </div>
  );
}

function SendIcon() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}
