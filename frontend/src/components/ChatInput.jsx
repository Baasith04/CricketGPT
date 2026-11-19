/**
 * ChatInput.jsx — Multi-line text input for composing messages.
 *
 * - Enter sends; Shift+Enter inserts a newline.
 * - Auto-grows up to ~5 lines.
 * - Integrates VoiceInput microphone button.
 */

import { useRef, useEffect, useCallback } from "react";
import { SendHorizonal } from "lucide-react";
import VoiceInput from "./VoiceInput";

/**
 * @param {{
 *   value: string,
 *   onChange: (val: string) => void,
 *   onSend: () => void,
 *   isLoading: boolean,
 * }} props
 */
export default function ChatInput({ value, onChange, onSend, isLoading }) {
  const textareaRef = useRef(null);

  // Auto-resize textarea without spurious scrollbars on placeholder wrap
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const nextHeight = Math.min(el.scrollHeight, 140);
    el.style.height = `${nextHeight}px`;
    el.style.overflowY = el.scrollHeight > 140 ? "auto" : "hidden";
  }, [value]);

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!isLoading && value.trim()) onSend();
      }
    },
    [isLoading, value, onSend]
  );

  const handleVoiceTranscript = useCallback(
    (text) => {
      onChange(value ? `${value} ${text}` : text);
      setTimeout(() => textareaRef.current?.focus(), 100);
    },
    [value, onChange]
  );

  const canSend = !isLoading && value.trim().length > 0 && value.length <= 500;

  return (
    <div
      className="flex-shrink-0 px-3 py-2.5 sm:px-6 sm:py-4
                 bg-primary-dark/65 backdrop-blur-md border-t border-white/15"
    >
      <div className="max-w-4xl mx-auto">
        <div
          className="flex items-end gap-2 bg-white/10 backdrop-blur-sm
                     border border-white/25 rounded-2xl px-2.5 py-2 sm:px-3 sm:py-2.5
                     focus-within:border-accent/80 focus-within:bg-white/15 transition-all duration-200 shadow-inner"
        >
          <VoiceInput onTranscript={handleVoiceTranscript} disabled={isLoading} />

          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about IPL…"
            rows={1}
            maxLength={500}
            disabled={isLoading}
            aria-label="Type your cricket question"
            className="flex-1 resize-none bg-transparent text-white placeholder-blue-100/60
                       text-sm sm:text-base font-medium leading-relaxed
                       focus:outline-none disabled:opacity-50 py-1
                       scrollbar-thin max-h-[140px]"
          />

          {value.length > 400 && (
            <span
              className={`flex-shrink-0 text-xs font-semibold self-end pb-1
                          ${value.length > 490 ? "text-red-300" : "text-blue-100/75"}`}
            >
              {value.length}/500
            </span>
          )}

          <button
            type="button"
            onClick={onSend}
            disabled={!canSend}
            title="Send message"
            aria-label="Send message"
            className="btn-send flex-shrink-0 w-9 h-9 flex items-center justify-center self-end"
          >
            <SendHorizonal size={18} />
          </button>
        </div>

        <p className="text-center text-blue-100/55 text-xs mt-2 hidden sm:block">
          Press <kbd className="font-semibold text-blue-100/80">Enter</kbd> to send ·{" "}
          <kbd className="font-semibold text-blue-100/80">Shift+Enter</kbd> for new line
        </p>
      </div>
    </div>
  );
}
