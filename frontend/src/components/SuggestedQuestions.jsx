/**
 * SuggestedQuestions.jsx — Welcome hero & clickable IPL prompt cards shown in the empty state.
 */

import { Sparkles, ArrowUpRight } from "lucide-react";

const QUESTIONS = [
  {
    emoji: "🏆",
    category: "Season Champion",
    text: "Who won IPL 2024?",
  },
  {
    emoji: "📋",
    category: "Match Scorecard",
    text: "Give me the IPL 2024 final scorecard.",
  },
  {
    emoji: "🏟️",
    category: "Playoff Match",
    text: "Give me the scorecard of the second qualifier in IPL 2024.",
  },
  {
    emoji: "🏏",
    category: "All-Time Batting",
    text: "Who scored the most runs in IPL history?",
  },
  {
    emoji: "🎯",
    category: "Season Bowling",
    text: "Who took the most wickets in IPL 2023?",
  },
  {
    emoji: "⭐",
    category: "Final MVP",
    text: "Who was the Player of the Match in the IPL 2024 final?",
  },
];

/**
 * @param {{ onSelect: (question: string) => void }} props
 */
export default function SuggestedQuestions({ onSelect }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-full px-4 py-6 sm:py-10 animate-[fadeIn_0.4s_ease-out]">
      {/* Hero welcome panel */}
      <div className="text-center max-w-2xl mb-6 sm:mb-8 px-4 py-5 sm:px-8 sm:py-6 rounded-3xl bg-primary-dark/55 backdrop-blur-md border border-white/15 shadow-xl shadow-blue-950/35">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-accent/15 border border-accent/40 text-accent text-xs font-bold tracking-wide uppercase mb-3">
          <Sparkles size={13} />
          <span>IPL Database · 2008–2026</span>
        </div>

        <h2 className="text-white text-2xl sm:text-3xl md:text-4xl font-extrabold tracking-tight mb-2.5">
          Ask anything about <span className="text-accent">IPL Cricket</span>
        </h2>

        <p className="text-blue-100/85 text-xs sm:text-sm md:text-base leading-relaxed">
          Full innings scorecards, playoff results, career leaderboards, and match analytics powered by SQL &amp; RAG.
        </p>
      </div>

      {/* Question cards grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 w-full max-w-4xl">
        {QUESTIONS.map(({ emoji, category, text }) => (
          <button
            type="button"
            key={text}
            onClick={() => onSelect(text)}
            className="question-card group flex flex-col justify-between min-h-[84px]"
          >
            <div className="flex items-center justify-between w-full mb-1.5">
              <span className="inline-flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-accent">
                <span className="text-sm">{emoji}</span>
                <span>{category}</span>
              </span>
              <ArrowUpRight
                size={14}
                className="text-blue-200/60 group-hover:text-accent group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform"
              />
            </div>
            <span className="text-white/95 group-hover:text-white text-sm font-medium leading-snug">
              {text}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
