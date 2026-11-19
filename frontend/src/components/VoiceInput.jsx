/**
 * VoiceInput.jsx — Microphone button powered by the Web Speech API.
 *
 * Shows a pulsing red ring + live interim transcript indicator while recording.
 * Calls onTranscript when a final result is received.
 */

import { Mic, MicOff, X } from "lucide-react";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";

/**
 * @param {{
 *   onTranscript: (text: string) => void,
 *   disabled: boolean,
 * }} props
 */
export default function VoiceInput({ onTranscript, disabled }) {
  const { isSupported, isListening, transcript, error, start, stop, clearError } =
    useSpeechRecognition({
      onResult: onTranscript,
    });

  if (!isSupported) return null; // hide on unsupported browsers

  const handleClick = () => {
    if (isListening) {
      stop();
    } else {
      start();
    }
  };

  return (
    <div className="relative flex items-center">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled}
        title={isListening ? "Stop recording" : "Start voice input"}
        aria-label={isListening ? "Stop recording" : "Voice input"}
        aria-pressed={isListening}
        className={`
          relative p-2.5 rounded-xl transition-all duration-150 active:scale-90
          disabled:opacity-40 disabled:cursor-not-allowed
          ${isListening
            ? "bg-red-500 text-white shadow-md shadow-red-500/40"
            : "text-blue-100 hover:text-white hover:bg-white/15"
          }
        `}
      >
        {isListening && (
          <span className="absolute inset-0 rounded-xl border-2 border-red-400 animate-ping opacity-60" />
        )}
        {isListening ? <MicOff size={18} /> : <Mic size={18} />}
      </button>

      {/* Live recording indicator */}
      {isListening && (
        <span
          role="status"
          className="absolute bottom-full left-0 mb-2.5 max-w-[260px] sm:max-w-xs truncate
                     bg-primary-dark/95 border border-accent/60 text-white text-xs font-medium
                     rounded-xl px-3 py-1.5 shadow-xl z-20 flex items-center gap-2"
        >
          <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse flex-shrink-0" />
          <span className="truncate">{transcript ? transcript : "Listening… speak your IPL question"}</span>
        </span>
      )}

      {/* Dismissible error tooltip anchored left so it stays inside viewport on mobile */}
      {error && !isListening && (
        <span
          role="alert"
          className="absolute bottom-full left-0 mb-2.5 w-64 text-left flex items-start justify-between gap-2
                     bg-red-950/95 border border-red-400/50 text-red-100 text-xs rounded-xl px-3 py-2 shadow-xl z-20"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={clearError}
            aria-label="Dismiss voice error"
            className="text-red-200 hover:text-white flex-shrink-0 mt-0.5"
          >
            <X size={13} />
          </button>
        </span>
      )}
    </div>
  );
}
