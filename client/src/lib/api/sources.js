import { api } from "@/lib/api/client";

/**
 * Financial sources API.
 * All calls are workspace-scoped server-side; the workspace is resolved from
 * the authenticated session and never accepted from the browser.
 */

export function listSources({ type, limit = 50, cursor, signal } = {}) {
  const params = new URLSearchParams();
  if (type) params.set("type", type);
  if (limit) params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);
  const query = params.toString();
  return api.get(`/api/sources${query ? `?${query}` : ""}`, { signal });
}

export function createSource(payload) {
  return api.post("/api/sources", payload);
}

export function getSource(sourceId, { signal } = {}) {
  return api.get(`/api/sources/${encodeURIComponent(sourceId)}`, { signal });
}
