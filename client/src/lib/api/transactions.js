import { api } from "@/lib/api/client";

/**
 * Transactions API — server-side filtering and cursor pagination only.
 * The browser never loads unbounded financial data.
 */

export function listTransactions(
  {
    sourceId,
    dateFrom,
    dateTo,
    currency,
    direction,
    status,
    type,
    search,
    limit = 25,
    cursor,
    signal,
  } = {}
) {
  const params = new URLSearchParams();
  if (sourceId) params.set("sourceId", sourceId);
  if (dateFrom) params.set("dateFrom", dateFrom);
  if (dateTo) params.set("dateTo", dateTo);
  if (currency) params.set("currency", currency);
  if (direction) params.set("direction", direction);
  if (status) params.set("status", status);
  if (type) params.set("type", type);
  if (search) params.set("search", search);
  if (limit) params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);
  const query = params.toString();
  return api.get(`/api/transactions${query ? `?${query}` : ""}`, { signal });
}

export function getTransaction(transactionId, { signal } = {}) {
  return api.get(`/api/transactions/${encodeURIComponent(transactionId)}`, { signal });
}

/**
 * Reconciliation evidence involving this transaction: the match groups it
 * belongs to, with score breakdowns and reasons from the engine.
 */
export function listTransactionMatches(transactionId, { limit = 5, cursor, signal } = {}) {
  const params = new URLSearchParams();
  if (limit) params.set("limit", String(limit));
  if (cursor) params.set("cursor", cursor);
  const query = params.toString();
  return api.get(
    `/api/transactions/${encodeURIComponent(transactionId)}/matches${query ? `?${query}` : ""}`,
    { signal }
  );
}
