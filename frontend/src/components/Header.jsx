/**
 * Header.jsx — CricketGPT top bar.
 * Shows branding, live backend status indicator, and a "New Chat" button.
 */

import { RotateCcw } from "lucide-react";

/**
 * @param {{
 *   onClearChat: () => void,
 *   isBackendAlive: boolean | null,
 *   messageCount: number,
 * }} props
 */
export default function Header({ onClearChat, isBackendAlive, messageCount }) {
  return (
    <header
      className="relative z-10 flex items-center justify-between px-3 py-2.5 sm:px-5 sm:py-3.5
                 bg-primary-dark/70 backdrop-blur-md border-b border-white/15 shadow-lg shadow-blue-950/20"
    >
      {/* ── Brand ── */}
      <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
        <div
          className="flex-shrink-0 w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-primary flex items-center justify-center
                     shadow-md shadow-blue-950/50 border-2 border-accent/80 overflow-hidden"
        >
          <img
            src="/cricket-ball.svg"
            alt="CricketGPT logo"
            className="w-6 h-6 sm:w-7 sm:h-7 select-none"
          />
        </div>

        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-white font-extrabold text-lg sm:text-xl md:text-2xl leading-tight tracking-tight">
              Cricket<span className="text-accent">GPT</span>
            </h1>
            <span className="hidden md:inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-accent/15 text-accent border border-accent/35">
              IPL AI
            </span>
          </div>
          <p className="text-blue-100/80 text-[11px] sm:text-xs font-medium truncate">
            Your AI-powered IPL assistant
          </p>
        </div>
      </div>

      {/* ── Right controls ── */}
      <div className="flex items-center gap-2 sm:gap-3 flex-shrink-0">
        <StatusBadge alive={isBackendAlive} />

        {messageCount > 0 && (
          <button
            type="button"
            onClick={onClearChat}
            title="New chat"
            aria-label="Clear chat"
            className="flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-xs sm:text-sm font-semibold
                       text-white bg-white/10 hover:bg-white/20 border border-white/20
                       hover:border-accent/60 active:scale-95 transition-all duration-150"
          >
            <RotateCcw size={14} />
            <span className="hidden sm:inline">New Chat</span>
          </button>
        )}
      </div>
    </header>
  );
}

function StatusBadge({ alive }) {
  if (alive === null) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-white/10 border border-white/15 text-blue-100">
        <span className="status-dot bg-blue-300 animate-pulse" />
        <span>Connecting…</span>
      </span>
    );
  }
  if (alive) {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 border border-emerald-400/35 text-emerald-200">
        <span className="status-dot bg-emerald-400 shadow-sm shadow-emerald-400/60" />
        <span>Online</span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/15 border border-amber-400/40 text-amber-200">
      <span className="status-dot bg-amber-400 animate-pulse" />
      <span>Waking up…</span>
    </span>
  );
}
