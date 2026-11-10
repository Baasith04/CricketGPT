/**
 * ChatWindow.jsx — Scrollable message list.
 *
 * Auto-scrolls to the bottom whenever messages or typing state changes.
 */

import { useEffect, useRef } from "react";
import ChatMessage from "./ChatMessage";
import TypingIndicator from "./TypingIndicator";

/**
 * @param {{
 *   messages: Array<{ id: string, role: "user"|"bot", content: string, timestamp: Date, isError?: boolean }>,
 *   isTyping: boolean,
 * }} props
 */
export default function ChatWindow({ messages, isTyping }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  return (
    <div
      className="chat-window flex-1 px-3 py-4 md:px-6 md:py-5 space-y-4 scrollbar-thin"
      role="log"
      aria-live="polite"
      aria-label="Chat messages"
    >
      {messages.map((msg) => (
        <ChatMessage
          key={msg.id}
          role={msg.role}
          content={msg.content}
          timestamp={msg.timestamp}
          isError={msg.isError}
        />
      ))}

      {isTyping && <TypingIndicator />}

      <div ref={bottomRef} aria-hidden="true" />
    </div>
  );
}

