/**
 * api.js — CricketGPT backend API client.
 *
 * Uses VITE_API_BASE_URL from frontend/.env. During local Vite development
 * (`vite dev`), requests use relative paths so Vite's dev-server proxy forwards
 * them to VITE_API_BASE_URL without triggering cross-origin CORS blocks.
 */

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
 * sendChatMessage — POST /api/chat
 *
 * Matches FastAPI schema:
 *   ChatRequest:  { question: string (1–500 chars) }
 *   ChatResponse: { question: string, answer: string }
 *
 * @param {string} question
 * @returns {Promise<{ question: string, answer: string }>}
 * @throws Error with a human-readable `.message`
 */
export async function sendChatMessage(question) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  let response;
  try {
    response = await fetch(`${BASE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
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
