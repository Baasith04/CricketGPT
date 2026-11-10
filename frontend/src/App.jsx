/**
 * App.jsx — CricketGPT main application.
 *
 * Manages global state: chat history, loading, backend health check.
 */

import { useState, useCallback, useEffect } from "react";
import { checkBackendHealth, sendChatMessage } from "./services/api";
import Header from "./components/Header";
import ChatWindow from "./components/ChatWindow";
import ChatInput from "./components/ChatInput";
import SuggestedQuestions from "./components/SuggestedQuestions";

/** Generates a simple unique message ID. */
let _msgId = 0;
function nextId() {
  return `msg-${Date.now()}-${++_msgId}`;
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isBackendAlive, setIsBackendAlive] = useState(null); // null = unknown

  // Check backend /health once on mount
  useEffect(() => {
    checkBackendHealth().then(setIsBackendAlive);
  }, []);

  /** Append a message to the history. */
  const addMessage = useCallback((role, content, isError = false) => {
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role, content, timestamp: new Date(), isError },
    ]);
  }, []);

  /** Submit a validated question string to the backend. */
  const submitQuestion = useCallback(
    async (rawQuestion) => {
      const question = rawQuestion.trim();
      if (!question || isLoading || question.length > 500) return;

      setInputValue("");
      addMessage("user", question);
      setIsLoading(true);

      try {
        const data = await sendChatMessage(question);
        addMessage("bot", data.answer);
        setIsBackendAlive(true);
      } catch (err) {
        const isAsleep =
          err.message.includes("waking up") || err.message.includes("timed out");
        if (isAsleep) setIsBackendAlive(false);
        addMessage("bot", `⚠️ ${err.message}`, true);
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, addMessage]
  );

  /** Send the current input value to the backend. */
  const handleSend = useCallback(() => {
    submitQuestion(inputValue);
  }, [inputValue, submitQuestion]);

  /** Handle a suggested question card click. */
  const handleSuggestedQuestion = useCallback(
    (question) => {
      submitQuestion(question);
    },
    [submitQuestion]
  );

  const handleClearChat = useCallback(() => {
    setMessages([]);
    setInputValue("");
  }, []);

  const isEmpty = messages.length === 0 && !isLoading;

  return (
    <div className="app-bg min-h-screen flex flex-col">
      {/* Fixed-height viewport layout (uses dvh for mobile browser bars) */}
      <div className="flex flex-col h-[100dvh] max-w-5xl mx-auto w-full">
        {/* ── Header ── */}
        <Header
          onClearChat={handleClearChat}
          isBackendAlive={isBackendAlive}
          messageCount={messages.length}
        />

        {/* ── Main content area ── */}
        <main className="flex flex-col flex-1 min-h-0">
          {isEmpty ? (
            /* Empty state: suggested questions */
            <div className="flex-1 overflow-y-auto scrollbar-thin">
              <SuggestedQuestions onSelect={handleSuggestedQuestion} />
            </div>
          ) : (
            /* Active chat */
            <ChatWindow messages={messages} isTyping={isLoading} />
          )}

          {/* ── Input bar ── */}
          <ChatInput
            value={inputValue}
            onChange={setInputValue}
            onSend={handleSend}
            isLoading={isLoading}
          />
        </main>
      </div>
    </div>
  );
}
