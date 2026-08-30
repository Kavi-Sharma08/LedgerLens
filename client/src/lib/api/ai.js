import { api } from "@/lib/api/client";

/**
 * AI Reconciliation Intelligence API — each call asks the Groq-backed AI agent
 * to explain an existing reconciliation result. The agent only ever reads
 * (via backend-authorized, workspace-scoped tools); it never changes anything.
 */

export function analyzeTransaction(transactionId, { signal } = {}) {
  return api.post(
    `/api/ai/transaction/${encodeURIComponent(transactionId)}/analyze`,
    undefined,
    { signal }
  );
}

export function analyzeMatch(matchId, { signal } = {}) {
  return api.post(
    `/api/ai/match/${encodeURIComponent(matchId)}/analyze`,
    undefined,
    { signal }
  );
}

export function analyzeException(exceptionId, { signal } = {}) {
  return api.post(
    `/api/ai/exception/${encodeURIComponent(exceptionId)}/analyze`,
    undefined,
    { signal }
  );
}

export function analyzeReconciliation(runId, { signal } = {}) {
  return api.post(
    `/api/ai/reconciliation/${encodeURIComponent(runId)}/analyze`,
    undefined,
    { signal }
  );
}

export function askLedgerLens(payload, { signal } = {}) {
  return api.post("/api/ai/ask", payload, { signal });
}
