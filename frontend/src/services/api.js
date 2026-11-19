/**
 * api.js — CricketGPT backend API client.
 *
 * Uses VITE_API_BASE_URL from frontend/.env. During local Vite development
 * (`vite dev`), requests use relative paths so Vite's dev-server proxy forwards
 * them to VITE_API_BASE_URL without triggering cross-origin CORS blocks.
 */

import { supabase } from "./supabase";

const ENV_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "")
  .trim()
  .replace(/\/+$/, "");

const BASE_URL = import.meta.env.DEV ? "" : ENV_BASE_URL;

/** Milliseconds to wait before aborting a chat request. */
const TIMEOUT_MS = 90_000; // 90 s — accounts for Render cold-start

/** Milliseconds to wait for a health check ping. */
const HEALTH_TIMEOUT_MS = 10_000;

/**
 * Returns true when the response status suggests the backend is waking up
 * from a Render free-tier cold-start (502/503/504).
 */
export function isRenderSleeping(status) {
  return status === 502 || status === 503 || status === 504;
}

/**
 * Safely parse a JSON response body, returning null if parsing fails.
 */
async function tryParseJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

/**
 * checkBackendHealth — GET /health
 *
 * Verifies the FastAPI service health endpoint returns HTTP 200 with
 * `{ status: "healthy", service: "CricketGPT" }`.
 *
 * @returns {Promise<boolean>}
 */
export async function checkBackendHealth() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);

  try {
    const response = await fetch(`${BASE_URL}/health`, {
      method: "GET",
      signal: controller.signal,
    });
    if (!response.ok) return false;
    const data = await tryParseJson(response);
    return data?.status === "healthy";
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Helper to get authenticated headers with current Supabase Bearer access token.
 */
async function getAuthHeaders() {
  const {
    data: { session },
    error: sessionError,
  } = await supabase.auth.getSession();

  if (sessionError || !session?.access_token) {
    throw new Error(
      "Your session has expired or you are not signed in. Please sign in to continue."
    );
  }

  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${session.access_token}`,
  };
}

/**
 * listConversations — GET /api/conversations
 * Lists all conversations for the authenticated user.
 */
export async function listConversations() {
  const headers = await getAuthHeaders();
  const response = await fetch(`${BASE_URL}/api/conversations`, {
    method: "GET",
    headers,
  });
  if (!response.ok) {
    throw new Error("Failed to load conversations.");
  }
  return await response.json();
}

/**
 * getConversation — GET /api/conversations/{conversation_id}
 * Retrieves a conversation and its messages.
 */
export async function getConversation(conversationId) {
  const headers = await getAuthHeaders();
  const response = await fetch(`${BASE_URL}/api/conversations/${conversationId}`, {
    method: "GET",
    headers,
  });
  if (!response.ok) {
    throw new Error("Failed to load conversation details.");
  }
  return await response.json();
}

/**
 * createConversation — POST /api/conversations
 * Creates a new conversation.
 */
export async function createConversation(title = null) {
  const headers = await getAuthHeaders();
  const response = await fetch(`${BASE_URL}/api/conversations`, {
    method: "POST",
    headers,
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    throw new Error("Failed to create conversation.");
  }
  return await response.json();
}

/**
 * updateConversationTitle — PATCH /api/conversations/{conversation_id}
 * Updates conversation title.
 */
export async function updateConversationTitle(conversationId, title) {
  const headers = await getAuthHeaders();
  const response = await fetch(`${BASE_URL}/api/conversations/${conversationId}`, {
    method: "PATCH",
    headers,
    body: JSON.stringify({ title }),
  });
  if (!response.ok) {
    throw new Error("Failed to update conversation title.");
  }
  return await response.json();
}

/**
 * deleteConversation — DELETE /api/conversations/{conversation_id}
 * Deletes a conversation and its messages.
 */
export async function deleteConversation(conversationId) {
  const headers = await getAuthHeaders();
  const response = await fetch(`${BASE_URL}/api/conversations/${conversationId}`, {
    method: "DELETE",
    headers,
  });
  if (!response.ok) {
    throw new Error("Failed to delete conversation.");
  }
  return await response.json();
}

/**
 * sendChatMessage — POST /api/chat
 *
 * Matches FastAPI schema:
 *   ChatRequest:  { question: string, conversation_id?: UUID, conversation_history?: [...] }
 *   ChatResponse: { question: string, answer: string, conversation_id?: UUID }
 *
 * @param {string} question
 * @param {string|null} [conversationId=null]
 * @param {Array<{ role: string, content: string, isError?: boolean }>} [conversationHistory=[]]
 * @returns {Promise<{ question: string, answer: string, conversation_id?: string }>}
 * @throws Error with a human-readable `.message`
 */
export async function sendChatMessage(
  question,
  conversationId = null,
  conversationHistory = []
) {
  // Retrieve the current Supabase session access token before making request
  const {
    data: { session },
    error: sessionError,
  } = await supabase.auth.getSession();

  if (sessionError || !session?.access_token) {
    throw new Error(
      "Your session has expired or you are not signed in. Please sign in to continue."
    );
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  const payload = { question };
  if (conversationId) {
    payload.conversation_id = conversationId;
  }
  if (Array.isArray(conversationHistory) && conversationHistory.length > 0) {
    payload.conversation_history = conversationHistory
      .filter((m) => !m.isError && m.content)
      .slice(-6)
      .map((m) => ({
        role: m.role === "bot" ? "assistant" : m.role,
        content: m.content,
      }));
  }

  let response;
  try {
    response = await fetch(`${BASE_URL}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error(
        "The request timed out. The server may be starting up — please try again in a moment."
      );
    }
    throw new Error(
      "Could not reach the CricketGPT server. Please check your connection."
    );
  } finally {
    clearTimeout(timer);
  }

  if (isRenderSleeping(response.status)) {
    throw new Error(
      "The server is waking up from sleep. Please try again in 15–30 seconds."
    );
  }

  if (response.status === 401) {
    throw new Error(
      "Authentication error: Your session has expired or is invalid. Please sign in again."
    );
  }

  if (response.status === 422) {
    throw new Error("Invalid request — question must be between 1 and 500 characters.");
  }

  if (response.status === 429) {
    throw new Error("Too many requests. Please wait a moment before asking again.");
  }

  if (!response.ok) {
    const errBody = await tryParseJson(response);
    const detail = typeof errBody?.detail === "string" ? errBody.detail : null;
    throw new Error(
      detail
        ? `Server error (HTTP ${response.status}): ${detail}`
        : `Server error (HTTP ${response.status}). Please try again.`
    );
  }

  const data = await tryParseJson(response);
  if (!data || typeof data.answer !== "string") {
    throw new Error("Received an unexpected response from the server.");
  }

  return data; // { question, answer }
}
