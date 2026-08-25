import { api } from "@/lib/api/client";

/**
 * Workspace audit log API.
 */

export function listAuditLogs({ action, userId, limit = 25, cursor, signal } = {}) {
  const params = new URLSearchParams();
  if (action) params.set("action", action);
  if (userId) params.set("user_id", userId);
  if (limit) params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);
  const query = params.toString();
  return api.get(`/api/audit${query ? `?${query}` : ""}`, { signal });
}
