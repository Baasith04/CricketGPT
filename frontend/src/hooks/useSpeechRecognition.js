/**
 * useSpeechRecognition.js — Browser Web Speech API hook.
 *
 * Returns controls and reactive state for speech-to-text.
 * Preferred locale: en-IN.
 */

import { useState, useEffect, useRef, useCallback } from "react";

const SpeechRecognition =
  typeof window !== "undefined"
    ? window.SpeechRecognition || window.webkitSpeechRecognition
    : null;

/**
 * @returns {{
 *   isSupported: boolean,
 *   isListening: boolean,
 *   transcript: string,
 *   error: string | null,
 *   start: () => void,
 *   stop: () => void,
 *   cancel: () => void,
 * }}
 */
export function useSpeechRecognition({ onResult } = {}) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState(null);
  const recognitionRef = useRef(null);

  const isSupported = Boolean(SpeechRecognition);

  const stop = useCallback(() => {
    try {
      recognitionRef.current?.stop();
    } catch {
      setIsListening(false);
    }
  }, []);

  const cancel = useCallback(() => {
    try {
      recognitionRef.current?.abort();
    } catch {
      // Ignore abort errors when not active
    }
    setIsListening(false);
    setTranscript("");
    setError(null);
  }, []);

  const start = useCallback(() => {
    if (!isSupported) {
      setError("Speech recognition is not supported in this browser. Try Chrome.");
      return;
    }
    setError(null);
    setTranscript("");

    const rec = new SpeechRecognition();
    rec.lang = "en-IN";
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.continuous = false;

    rec.onstart = () => setIsListening(true);

    rec.onresult = (event) => {
      const result = event.results[event.results.length - 1];
      const text = result[0].transcript;
      setTranscript(text);
      if (result.isFinal) {
        onResult?.(text);
        setIsListening(false);
      }
    };

    rec.onerror = (event) => {
      const msg =
        event.error === "not-allowed"
          ? "Microphone access was denied. Please allow it in browser settings."
          : event.error === "no-speech"
          ? "No speech detected. Please try again."
          : `Speech error: ${event.error}`;
      setError(msg);
      setIsListening(false);
    };

    rec.onend = () => setIsListening(false);

    recognitionRef.current = rec;
    try {
      rec.start();
    } catch {
      setError("Unable to start microphone. Please try again.");
      setIsListening(false);
    }
  }, [isSupported, onResult]);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Auto-dismiss transient speech error tooltips after 5 seconds
  useEffect(() => {
    if (!error) return;
    const timer = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(timer);
  }, [error]);

  useEffect(() => {
    return () => {
      try {
        recognitionRef.current?.abort();
      } catch {
        // Ignore cleanup errors
      }
    };
  }, []);

  return { isSupported, isListening, transcript, error, start, stop, cancel, clearError };
}
