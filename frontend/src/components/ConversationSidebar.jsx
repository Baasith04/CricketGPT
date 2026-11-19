/**
 * ConversationSidebar.jsx — CricketGPT persistent chat history drawer.
 *
 * Features:
 * - New Chat button at top
 * - List previous conversations with title and relative timestamp
 * - Select conversation to view/continue
 * - Delete conversation with confirmation
 * - Loading, empty, and error states
 * - Mobile responsive drawer with smooth backdrop
 */

import { useState } from "react";
import { Plus, MessageSquare, Trash2, X, AlertCircle, RefreshCw } from "lucide-react";

/**
 * Format relative date (e.g. "Today", "Yesterday", or "Oct 24")
 */
function formatTime(isoString) {
  if (!isoString) return "";
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffHours = diffMs / (1000 * 60 * 60);

    if (diffHours < 24 && date.getDate() === now.getDate()) {
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    if (date.getDate() === yesterday.getDate()) {
      return "Yesterday";
    }
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

export default function ConversationSidebar({
  isOpen,
  onClose,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  isLoading,
  error,
  onRetry,
}) {
  const [deletingId, setDeletingId] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

  const handleDeleteClick = (e, convId) => {
    e.stopPropagation();
    setConfirmDeleteId(convId);
  };

  const handleConfirmDelete = async (e, convId) => {
    e.stopPropagation();
    setDeletingId(convId);
    try {
      await onDeleteConversation(convId);
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  };

  const handleCancelDelete = (e) => {
    e.stopPropagation();
    setConfirmDeleteId(null);
  };

  return (
    <>
      {/* ── Mobile Backdrop ── */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm transition-opacity md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* ── Sidebar panel ── */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-72 sm:w-80 bg-primary-dark/95 backdrop-blur-md
                    border-r border-white/10 flex flex-col shadow-2xl transition-transform duration-300 ease-in-out
                    ${isOpen ? "translate-x-0" : "-translate-x-full"}`}
        aria-label="Conversation history"
      >
        {/* Header / Brand */}
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <div className="flex items-center gap-2">
            <MessageSquare size={18} className="text-accent" />
            <h2 className="text-white font-bold text-sm sm:text-base">Your Conversations</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-blue-200 hover:text-white hover:bg-white/10 transition-colors"
            aria-label="Close sidebar"
          >
            <X size={18} />
          </button>
        </div>

        {/* New Chat Button */}
        <div className="p-3">
          <button
            type="button"
            onClick={() => {
              onNewChat();
              if (window.innerWidth < 768) onClose();
            }}
            className="w-full flex items-center justify-center gap-2 rounded-xl py-2.5 px-4
                       bg-accent hover:bg-accent-hover text-blue-950 font-bold text-sm
                       shadow-md shadow-accent/20 hover:shadow-accent/40 active:scale-[0.98] transition-all"
          >
            <Plus size={16} className="stroke-[2.5]" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-1 scrollbar-thin">
          {isLoading ? (
            <div className="p-6 text-center text-blue-200/70 text-xs flex flex-col items-center gap-2">
              <RefreshCw size={18} className="animate-spin text-accent" />
              <span>Loading conversations…</span>
            </div>
          ) : error ? (
            <div className="p-4 mx-2 rounded-xl bg-red-500/10 border border-red-500/20 text-red-200 text-xs">
              <div className="flex items-center gap-1.5 font-semibold text-red-300 mb-1">
                <AlertCircle size={14} />
                <span>Could not load history</span>
              </div>
              <p className="mb-2">{error}</p>
              {onRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  className="px-2.5 py-1 rounded bg-white/10 hover:bg-white/20 text-white font-medium text-xs transition"
                >
                  Retry
                </button>
              )}
            </div>
          ) : conversations.length === 0 ? (
            <div className="p-8 text-center text-blue-200/60 text-xs flex flex-col items-center gap-2">
              <MessageSquare size={28} className="text-blue-300/30" />
              <p className="font-medium text-blue-100/70">No conversations yet</p>
              <p className="text-[11px] text-blue-200/50">
                Ask a question about IPL to start saving your chat history!
              </p>
            </div>
          ) : (
            conversations.map((conv) => {
              const isActive = conv.id === activeConversationId;
              const isConfirming = confirmDeleteId === conv.id;
              const isDeleting = deletingId === conv.id;

              return (
                <div
                  key={conv.id}
                  onClick={() => {
                    if (isConfirming) return;
                    onSelectConversation(conv.id);
                    if (window.innerWidth < 768) onClose();
                  }}
                  className={`group relative flex items-center justify-between p-2.5 rounded-xl cursor-pointer
                              transition-all duration-150 border
                              ${
                                isActive
                                  ? "bg-white/15 border-accent/60 shadow-sm text-white"
                                  : "hover:bg-white/10 border-transparent text-blue-100/80 hover:text-white"
                              }`}
                >
                  <div className="min-w-0 flex-1 pr-2">
                    <p className="text-xs font-semibold truncate leading-snug">
                      {conv.title || "IPL Chat"}
                    </p>
                    <p className="text-[10px] text-blue-200/50 mt-0.5">
                      {formatTime(conv.updated_at || conv.created_at)}
                    </p>
                  </div>

                  {/* Actions / Delete */}
                  {isConfirming ? (
                    <div
                      className="flex items-center gap-1 bg-primary-dark/95 border border-red-500/40 rounded-lg p-1 text-[11px]"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        type="button"
                        onClick={(e) => handleConfirmDelete(e, conv.id)}
                        disabled={isDeleting}
                        className="px-1.5 py-0.5 rounded bg-red-600 hover:bg-red-700 text-white font-bold"
                      >
                        {isDeleting ? "…" : "Delete"}
                      </button>
                      <button
                        type="button"
                        onClick={handleCancelDelete}
                        className="px-1.5 py-0.5 rounded hover:bg-white/20 text-blue-200"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={(e) => handleDeleteClick(e, conv.id)}
                      title="Delete conversation"
                      aria-label="Delete conversation"
                      className="opacity-0 group-hover:opacity-100 focus:opacity-100 p-1.5 rounded-lg
                                 text-blue-200/60 hover:text-red-400 hover:bg-red-500/10 transition-all"
                    >
                      <Trash2 size={13} />
                    </button>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer info */}
        <div className="p-3 border-t border-white/10 text-center">
          <p className="text-[11px] text-blue-200/40 font-medium">
            Saved securely in Supabase
          </p>
        </div>
      </aside>
    </>
  );
}
