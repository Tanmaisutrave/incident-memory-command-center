const BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
export async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 95000);
  try {
    const response = await fetch(`${BASE}/api${path}`, {
      ...options,
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) {
      const message = Array.isArray(data.detail)
        ? data.detail
            .map((x) => `${x.loc.slice(1).join(".")}: ${x.msg}`)
            .join("; ")
        : data.detail;
      throw new Error(message || `Request failed (${response.status})`);
    }
    return data;
  } catch (error) {
    if (error.name === "AbortError")
      throw new Error(
        "This request timed out. Check the incident list before retrying; the server may still be finishing.",
      );
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}
export const post = (path, data = {}) =>
  request(path, { method: "POST", body: JSON.stringify(data) });
