import { api } from "@/lib/api/client";

/**
 * Reconciliation runs API.
 */

export function listRuns({ limit = 20, cursor, signal } = {}) {
  const params = new URLSearchParams();
  if (limit) params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);
  const query = params.toString();
  return api.get(`/api/reconciliations${query ? `?${query}` : ""}`, { signal });
}

export function getRun(runId, { signal } = {}) {
  return api.get(`/api/reconciliations/${encodeURIComponent(runId)}`, { signal });
}

/**
 * Runs a deterministic reconciliation across the given sources.
 * payload: { sourceIds: [id, id, ...] } — at least two, all in this workspace.
 */
export function startRun(payload) {
  return api.post("/api/reconciliations", payload);
}

export function listRunMatches(
  runId,
  { statuses, limit = 25, cursor, signal } = {}
) {
  const params = new URLSearchParams();
  // Repeated query params (?status=A&status=B) mirror FastAPI's list parsing.
  for (const status of statuses ?? []) {
    if (status) params.append("status", status);
  }
  if (limit) params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);
  const query = params.toString();
  return api.get(
    `/api/reconciliations/${encodeURIComponent(runId)}/matches${query ? `?${query}` : ""}`,
    { signal }
  );
}

export function listRunExceptions(
  runId,
  { status, limit = 25, cursor, signal } = {}
) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (limit) params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);
  const query = params.toString();
  return api.get(
    `/api/reconciliations/${encodeURIComponent(runId)}/exceptions${query ? `?${query}` : ""}`,
    { signal }
  );
}

export function listRunUnmatched(runId, { limit = 25, cursor, signal } = {}) {
  const params = new URLSearchParams();
  if (limit) params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);
  const query = params.toString();
  return api.get(
    `/api/reconciliations/${encodeURIComponent(runId)}/unmatched${query ? `?${query}` : ""}`,
    { signal }
  );
}

export function approveMatch(runId, matchId, { note = "", signal } = {}) {
  return api.post(
    `/api/reconciliations/${encodeURIComponent(runId)}/matches/${encodeURIComponent(matchId)}/approve`,
    { note },
    { signal }
  );
}

export function rejectMatch(runId, matchId, { note = "", signal } = {}) {
  return api.post(
    `/api/reconciliations/${encodeURIComponent(runId)}/matches/${encodeURIComponent(matchId)}/reject`,
    { note },
    { signal }
  );
}
