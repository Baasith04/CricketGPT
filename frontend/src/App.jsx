/**
 * App.jsx — CricketGPT main application.
 *
 * Manages global state: chat messages, active conversation, persistent history,
 * loading states, and backend health check.
 */

import { useState, useCallback, useEffect } from "react";
import {
  checkBackendHealth,
  deleteConversation,
  getConversation,
  listConversations,
  sendChatMessage,
} from "./services/api";
import { useAuth } from "./context/AuthContext";
import Header from "./components/Header";
import ChatWindow from "./components/ChatWindow";
import ChatInput from "./components/ChatInput";
import SuggestedQuestions from "./components/SuggestedQuestions";
import ConversationSidebar from "./components/ConversationSidebar";

const STORAGE_ACTIVE_CONV_KEY = "cricketgpt_active_conversation_id";

/** Generates a simple unique message ID. */
let _msgId = 0;
function nextId() {
  return `msg-${Date.now()}-${++_msgId}`;
}

export default function App() {
  const { user } = useAuth();

  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isBackendAlive, setIsBackendAlive] = useState(null); // null = unknown

  // Sidebar & Persistent Conversations state
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [isConversationsLoading, setIsConversationsLoading] = useState(false);
  const [conversationsError, setConversationsError] = useState(null);

  // Check backend /health once on mount
  useEffect(() => {
    checkBackendHealth().then(setIsBackendAlive);
  }, []);

  /** Fetch the list of conversations from the backend. */
  const fetchConversations = useCallback(async () => {
    if (!user) {
      setConversations([]);
      return;
    }
    setIsConversationsLoading(true);
    setConversationsError(null);
    try {
      const data = await listConversations();
      setConversations(data || []);
      return data;
    } catch (err) {
      setConversationsError(err.message || "Failed to load conversations");
      return null;
    } finally {
      setIsConversationsLoading(false);
    }
  }, [user]);

  // Load conversations and restore active conversation on login/mount
  useEffect(() => {
    if (!user) {
      setConversations([]);
      setActiveConversationId(null);
      setMessages([]);
      localStorage.removeItem(STORAGE_ACTIVE_CONV_KEY);
      return;
    }

    fetchConversations().then((convList) => {
      const savedId = localStorage.getItem(STORAGE_ACTIVE_CONV_KEY);
      if (savedId && convList && convList.some((c) => c.id === savedId)) {
        loadConversationMessages(savedId);
      }
    });
  }, [user, fetchConversations]);

  /** Load messages for a specific conversation. */
  const loadConversationMessages = useCallback(async (convId) => {
    setIsLoading(true);
    try {
      const detail = await getConversation(convId);
      if (detail && Array.isArray(detail.messages)) {
        const mapped = detail.messages.map((m) => ({
          id: m.id || nextId(),
          role: m.role === "assistant" ? "bot" : "user",
          content: m.content,
          timestamp: new Date(m.created_at || Date.now()),
          isError: false,
        }));
        setMessages(mapped);
        setActiveConversationId(convId);
        localStorage.setItem(STORAGE_ACTIVE_CONV_KEY, convId);
      }
    } catch (err) {
      console.error("Failed to load conversation messages:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  /** Append a message to the history. */
  const addMessage = useCallback((role, content, isError = false) => {
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role, content, timestamp: new Date(), isError },
    ]);
  }, []);

  /** Start a fresh new chat session. */
  const handleNewChat = useCallback(() => {
    setActiveConversationId(null);
    setMessages([]);
    setInputValue("");
    localStorage.removeItem(STORAGE_ACTIVE_CONV_KEY);
  }, []);

  /** Handle deleting a conversation. */
  const handleDeleteConversation = useCallback(
    async (convId) => {
      try {
        await deleteConversation(convId);
        setConversations((prev) => prev.filter((c) => c.id !== convId));
        if (activeConversationId === convId) {
          handleNewChat();
        }
      } catch (err) {
        console.error("Delete conversation error:", err);
      }
    },
    [activeConversationId, handleNewChat]
  );

  /** Submit a validated question string to the backend. */
  const submitQuestion = useCallback(
    async (rawQuestion) => {
      const question = rawQuestion.trim();
      if (!question || isLoading || question.length > 500) return;

      setInputValue("");
      addMessage("user", question);
      setIsLoading(true);

      try {
        const data = await sendChatMessage(question, activeConversationId, messages);
        addMessage("bot", data.answer);
        setIsBackendAlive(true);

        // If a new conversation was created on the backend, store its ID
        if (data.conversation_id && data.conversation_id !== activeConversationId) {
          setActiveConversationId(data.conversation_id);
          localStorage.setItem(STORAGE_ACTIVE_CONV_KEY, data.conversation_id);
          fetchConversations();
        }
      } catch (err) {
        const isAsleep =
          err.message.includes("waking up") || err.message.includes("timed out");
        if (isAsleep) setIsBackendAlive(false);
        addMessage("bot", `⚠️ ${err.message}`, true);
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, addMessage, activeConversationId, messages, fetchConversations]
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

  const isEmpty = messages.length === 0 && !isLoading;

  return (
    <div className="app-bg min-h-screen flex flex-col">
      {/* ── Persistent History Sidebar ── */}
      {user && (
        <ConversationSidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          conversations={conversations}
          activeConversationId={activeConversationId}
          onSelectConversation={(id) => {
            loadConversationMessages(id);
            setIsSidebarOpen(false);
          }}
          onNewChat={handleNewChat}
          onDeleteConversation={handleDeleteConversation}
          isLoading={isConversationsLoading}
          error={conversationsError}
          onRetry={fetchConversations}
        />
      )}

      {/* Fixed-height viewport layout (uses dvh for mobile browser bars) */}
      <div className="flex flex-col h-[100dvh] max-w-5xl mx-auto w-full">
        {/* ── Header ── */}
        <Header
          onClearChat={handleNewChat}
          isBackendAlive={isBackendAlive}
          messageCount={messages.length}
          onToggleSidebar={() => setIsSidebarOpen((v) => !v)}
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
