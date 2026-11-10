/**
 * ChatMessage.jsx — Renders a single chat message bubble.
 *
 * User messages: right-aligned, royal blue pill with yellow avatar.
 * Bot messages: left-aligned, crisp white card with full markdown + GFM tables.
 */

import { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy, Check, User } from "lucide-react";

/**
 * @param {{
 *   role: "user" | "bot",
 *   content: string,
 *   timestamp: Date,
 *   isError?: boolean,
 * }} props
 */
export default function ChatMessage({ role, content, timestamp, isError }) {
  const isUser = role === "user";

  return (
    <div className={`flex items-end gap-2 sm:gap-2.5 msg-enter ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      <Avatar role={role} />

      {/* Bubble container — min-w-0 allows wide scorecard tables to scroll horizontally inside */}
      <div className={`min-w-0 max-w-[88%] sm:max-w-[82%] md:max-w-[78%] flex flex-col ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`
            w-full rounded-2xl px-3.5 py-2.5 sm:px-4 sm:py-3 shadow-lg shadow-blue-950/20
            ${isUser
              ? "bg-primary text-white border border-blue-400/35 rounded-br-sm"
              : isError
              ? "bg-red-50/95 border border-red-200 rounded-bl-sm"
              : "bg-white/95 backdrop-blur-md border border-blue-100 rounded-bl-sm"
            }
          `}
        >
          {isUser ? (
            <p className="text-sm sm:text-[15px] font-medium leading-relaxed whitespace-pre-wrap break-words">
              {content}
            </p>
          ) : (
            <BotContent content={content} isError={isError} />
          )}
        </div>

        {/* Timestamp + copy */}
        <div className={`flex items-center gap-2 mt-1 px-1 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
          <span className="text-[11px] text-blue-100/75 font-medium">
            {formatTime(timestamp)}
          </span>
          {!isUser && !isError && <CopyButton text={content} />}
        </div>
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function Avatar({ role }) {
  if (role === "user") {
    return (
      <div
        className="flex-shrink-0 w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-accent flex items-center justify-center
                   shadow-md border border-yellow-200 self-end mb-5"
        aria-hidden="true"
      >
        <User size={15} className="text-primary-dark stroke-[2.5]" />
      </div>
    );
  }
  return (
    <div
      className="flex-shrink-0 w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-primary flex items-center justify-center
                 shadow-md shadow-blue-950/40 border border-accent/70 self-end mb-5 overflow-hidden"
      aria-hidden="true"
    >
      <img src="/cricket-ball.svg" alt="" className="w-4 h-4 sm:w-5 sm:h-5 select-none" />
    </div>
  );
}

function BotContent({ content, isError }) {
  return (
    <div className={`markdown-body text-sm sm:text-[15px] ${isError ? "text-red-700" : "text-slate-800"}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ children }) => (
            <div className="table-wrapper">
              <table>{children}</table>
            </div>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline hover:text-primary-light"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API not available; silently ignore
    }
  }, [text]);

  return (
    <button
      type="button"
      onClick={handleCopy}
      title={copied ? "Copied!" : "Copy response"}
      aria-label={copied ? "Copied" : "Copy response"}
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium
                 text-blue-100/80 hover:text-white hover:bg-white/15 transition-colors"
    >
      {copied ? (
        <>
          <Check size={12} className="text-emerald-300" />
          <span className="text-emerald-300">Copied</span>
        </>
      ) : (
        <>
          <Copy size={12} />
          <span>Copy</span>
        </>
      )}
    </button>
  );
}

/* ── Helpers ── */

function formatTime(date) {
  if (!date) return "";
  return date.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}
