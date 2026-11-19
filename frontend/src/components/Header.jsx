/**
 * Header.jsx — CricketGPT top bar.
 * Shows branding, live backend status, New Chat button, and a user avatar menu.
 *
 * The user menu (dropdown) replaces the previous standalone Sign Out button.
 * It contains:
 *   - User avatar / initials
 *   - Display name + email
 *   - My Account link → /account
 *   - Sign Out
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { RotateCcw, LogOut, User, Settings, ChevronDown, PanelLeft } from "lucide-react";
import { useAuth } from "../context/AuthContext";

/** ── User avatar — shows photo, initials, or generic icon ── */
function UserAvatar({ user, avatarUrl, size = "sm" }) {
  const displayName =
    user?.user_metadata?.full_name ??
    user?.email?.split("@")[0] ??
    "";

  const initials = displayName
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join("");

  const dim = size === "sm" ? "w-8 h-8 text-xs" : "w-10 h-10 text-sm";

  return (
    <div
      className={`${dim} rounded-full border-2 border-accent/70 bg-primary
                  flex items-center justify-center overflow-hidden select-none flex-shrink-0`}
    >
      {avatarUrl ? (
        <img src={avatarUrl} alt={displayName} className="w-full h-full object-cover" />
      ) : initials ? (
        <span className="text-white font-bold leading-none">{initials}</span>
      ) : (
        <User size={size === "sm" ? 15 : 18} className="text-blue-100/70" />
      )}
    </div>
  );
}

/** ── User dropdown menu ── */
function UserMenu({ user, signOut }) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (!menuRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const handleSignOut = useCallback(async () => {
    setOpen(false);
    try { await signOut(); } catch { /* ignore */ }
  }, [signOut]);

  const displayName =
    user?.user_metadata?.full_name ??
    user?.email?.split("@")[0] ??
    "Account";

  const avatarUrl = user?.user_metadata?.avatar_url ?? null;

  return (
    <div className="relative" ref={menuRef}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="true"
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-xl px-1.5 py-1 sm:px-2 sm:py-1.5
                   hover:bg-white/10 border border-transparent hover:border-white/20
                   active:scale-95 transition-all duration-150"
      >
        <UserAvatar user={user} avatarUrl={avatarUrl} size="sm" />
        <ChevronDown
          size={12}
          className={`text-blue-100/60 transition-transform duration-200 hidden sm:block ${open ? "rotate-180" : ""}`}
        />
      </button>

      {/* Dropdown panel */}
      {open && (
        <div
          className="absolute right-0 top-full mt-2 w-60 z-50
                     bg-primary-dark/95 backdrop-blur-xl
                     border border-white/15 rounded-2xl shadow-2xl shadow-blue-950/60
                     overflow-hidden animate-fade-in"
        >
          {/* User identity header */}
          <div className="px-4 py-3.5 border-b border-white/10 flex items-center gap-3">
            <UserAvatar user={user} avatarUrl={avatarUrl} size="lg" />
            <div className="min-w-0">
              <p className="text-white font-semibold text-sm truncate">{displayName}</p>
              <p className="text-blue-100/50 text-xs truncate">{user?.email}</p>
            </div>
          </div>

          {/* Menu items */}
          <div className="py-1.5">
            <Link
              to="/account"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 w-full px-4 py-2.5
                         text-blue-100/80 hover:text-white hover:bg-white/8
                         text-sm font-medium transition-colors duration-150"
            >
              <Settings size={15} className="text-blue-300/70" />
              My Account
            </Link>

            <button
              type="button"
              onClick={handleSignOut}
              className="flex items-center gap-2.5 w-full px-4 py-2.5
                         text-blue-100/80 hover:text-red-300 hover:bg-red-500/10
                         text-sm font-medium transition-colors duration-150"
            >
              <LogOut size={15} className="text-blue-300/70" />
              Sign Out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Main Header ─── */

/**
 * @param {{
 *   onClearChat: () => void,
 *   isBackendAlive: boolean | null,
 *   messageCount: number,
 * }} props
 */
export default function Header({ onClearChat, isBackendAlive, messageCount, onToggleSidebar }) {
  const { user, signOut } = useAuth();

  return (
    <header
      className="relative z-10 flex items-center justify-between px-3 py-2.5 sm:px-5 sm:py-3.5
                 bg-primary-dark/70 backdrop-blur-md border-b border-white/15 shadow-lg shadow-blue-950/20"
    >
      {/* ── Brand & Sidebar Toggle ── */}
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        {user && onToggleSidebar && (
          <button
            type="button"
            onClick={onToggleSidebar}
            title="Chat History"
            aria-label="Toggle chat history"
            className="p-1.5 sm:p-2 rounded-xl text-blue-100 hover:text-white bg-white/10 hover:bg-white/20
                       border border-white/20 hover:border-accent/60 active:scale-95 transition-all flex-shrink-0"
          >
            <PanelLeft size={18} />
          </button>
        )}

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

        {/* User avatar / dropdown menu */}
        {user && <UserMenu user={user} signOut={signOut} />}
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
