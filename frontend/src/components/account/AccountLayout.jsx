/**
 * AccountLayout.jsx
 * Page shell for /account — full-height app background with a
 * top bar (back link) and a centred, scrollable settings card.
 */

import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export default function AccountLayout({ children }) {
  return (
    <div className="app-bg min-h-screen">
      {/* Top bar */}
      <div className="bg-primary-dark/70 backdrop-blur-md border-b border-white/15 shadow-lg shadow-blue-950/20">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-3 flex items-center gap-3">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-blue-100/70 hover:text-white
                       text-sm font-medium transition-colors duration-150"
          >
            <ArrowLeft size={16} />
            <span>Back to CricketGPT</span>
          </Link>

          <span className="text-white/20">|</span>

          <div className="flex items-center gap-2">
            <img src="/cricket-ball.svg" alt="" className="w-5 h-5 select-none" />
            <span className="text-white font-bold text-sm">
              Cricket<span className="text-accent">GPT</span>
              <span className="text-blue-100/50 font-normal ml-1.5">/ Account</span>
            </span>
          </div>
        </div>
      </div>

      {/* Page body */}
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 pb-16">
        <h1 className="text-white font-extrabold text-2xl sm:text-3xl mb-2">Account Settings</h1>
        <p className="text-blue-100/60 text-sm mb-8">Manage your profile, password and email.</p>

        <div className="flex flex-col gap-5">
          {children}
        </div>
      </div>
    </div>
  );
}
