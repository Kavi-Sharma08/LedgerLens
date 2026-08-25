import { api } from "@/lib/api/client";

/**
 * Workspace-wide exceptions feed (the Exceptions screen).
 */

export function listExceptions({ status, limit = 25, cursor, signal } = {}) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (limit) params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);
  const query = params.toString();
  return api.get(`/api/exceptions${query ? `?${query}` : ""}`, { signal });
}

export function assignException(exceptionId, assignedTo, { signal } = {}) {
  return api.patch(
    `/api/exceptions/${encodeURIComponent(exceptionId)}/assign`,
    { assignedTo },
    { signal }
  );
}

export function updateExceptionStatus(exceptionId, status, { signal } = {}) {
  return api.patch(
    `/api/exceptions/${encodeURIComponent(exceptionId)}/status`,
    { status },
    { signal }
  );
}

export function addExceptionNote(exceptionId, text, { signal } = {}) {
  return api.post(
    `/api/exceptions/${encodeURIComponent(exceptionId)}/notes`,
    { text },
    { signal }
  );
}
