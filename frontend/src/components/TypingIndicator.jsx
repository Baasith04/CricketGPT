/**
 * TypingIndicator.jsx — Animated three-dot "bot is thinking" indicator.
 */

export default function TypingIndicator() {
  return (
    <div className="flex items-end gap-2 sm:gap-2.5 msg-enter">
      {/* Avatar */}
      <div
        className="flex-shrink-0 w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-primary flex items-center justify-center
                   shadow-md shadow-blue-950/40 border border-accent/70 overflow-hidden"
        aria-hidden="true"
      >
        <img src="/cricket-ball.svg" alt="" className="w-4 h-4 sm:w-5 sm:h-5 select-none" />
      </div>

      {/* Bubble */}
      <div
        className="bg-white/95 backdrop-blur-md rounded-2xl rounded-bl-sm px-4 py-3
                   shadow-lg shadow-blue-950/20 border border-blue-100 flex items-center gap-1.5"
        aria-label="CricketGPT is thinking"
      >
        <span className="typing-dot w-2 h-2 rounded-full bg-primary/70" />
        <span className="typing-dot w-2 h-2 rounded-full bg-primary/70" />
        <span className="typing-dot w-2 h-2 rounded-full bg-primary/70" />
      </div>
    </div>
  );
}
