/**
 * api.js — Typed fetch wrapper.
 *
 * Features
 * --------
 * - Reads response as text first, then tries JSON.parse; never throws on
 *   non-JSON bodies (shows "Server error (status)" instead).
 * - Checks response.ok before returning data; extracts detail from Pydantic
 *   validation errors (array) or plain strings.
 * - Merges caller-supplied headers with Content-Type.
 * - Sends X-API-Key from VITE_API_KEY env var when present.
 * - Surfaces X-Request-ID in error messages so engineers can trace backend logs.
 * - Exports `get`, `post`, `del` convenience wrappers.
 */

const BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const API_KEY = import.meta.env.VITE_API_KEY || "";

/**
 * Core fetch wrapper. Never silently swallows errors.
 * @param {string} path  – path relative to /api, e.g. "/incidents"
 * @param {RequestInit} options
 */
export async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 95_000);

  const extraHeaders = options.headers || {};
  const baseHeaders = { "Content-Type": "application/json" };
  if (API_KEY) baseHeaders["X-API-Key"] = API_KEY;

  try {
    const response = await fetch(`${BASE}/api${path}`, {
      ...options,
      headers: { ...baseHeaders, ...extraHeaders },
      signal: controller.signal,
    });

    // Always read as text — some error responses are not JSON
    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }

    if (!response.ok) {
      const reqId = response.headers.get("x-request-id");
      const reqNote = reqId ? ` [request-id: ${reqId}]` : "";

      let message;
      if (data?.detail) {
        message = Array.isArray(data.detail)
          ? data.detail
              .map((x) => `${(x.loc || []).slice(1).join(".")}: ${x.msg}`)
              .join("; ")
          : String(data.detail);
      } else if (data?.message) {
        message = String(data.message);
      } else if (text && text.length < 300) {
        message = text;
      } else {
        message = `Server error (${response.status})`;
      }

      throw new Error(message + reqNote);
    }

    // If response.ok but body was not JSON (e.g. empty 204) return null
    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(
        "This request timed out after 95 s. " +
          "Check the incident list before retrying — the server may still be processing.",
      );
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

/** GET /api{path} */
export const get = (path, opts = {}) => request(path, { method: "GET", ...opts });

/** POST /api{path} with JSON body */
export const post = (path, data = {}, opts = {}) =>
  request(path, { method: "POST", body: JSON.stringify(data), ...opts });

/** DELETE /api{path} */
export const del = (path, opts = {}) => request(path, { method: "DELETE", ...opts });
