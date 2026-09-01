"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { X, RotateCcw, ScanSearch, CornerDownLeft } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AiAnswer, Spinner, ErrorState } from "@/components/domain/ai-analysis";
import { useDashboard } from "@/components/common/dashboard-context";
import { useAiContext } from "@/components/common/ai-context";
import { askLedgerLens } from "@/lib/api/ai";
import { formatCount } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * LedgerLens — Reconciliation intelligence.
 *
 * A workspace-level investigation assistant. It answers questions about the
 * reconciliation records already inside the active workspace using
 * backend-authorized, workspace-scoped tools — it never alters any state and
 * only ever explains the deterministic reconciliation results.
 *
 * UX details:
 *  - Escape or clicking outside the panel closes it.
 *  - The close button is always visible in the header.
 *  - Starter prompts only appear while the conversation is empty.
 *  - Focus moves into the composer on open and returns to the launcher on close.
 */
export function AskLedgerLens() {
  const { can } = useDashboard();
  const { aiContext, copilotOpen, setCopilotOpen } = useAiContext();
  const [question, setQuestion] = useState("");
  const [thread, setThread] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const inputRef = useRef(null);
  const panelRef = useRef(null);
  const launcherRef = useRef(null);
  const bottomRef = useRef(null);
  const abortControllerRef = useRef(null);

  const canView = Boolean(can.viewData);

  // Auto-reset conversation when active context changes (prevents cross-entity
  // context bleed).
  const contextKey = `${aiContext.reconciliationRunId || ""}:${aiContext.transactionId || ""}:${aiContext.matchId || ""}:${aiContext.exceptionId || ""}`;
  const prevKeyRef = useRef(contextKey);

  useEffect(() => {
    if (prevKeyRef.current !== contextKey) {
      setThread([]);
      setError(null);
      prevKeyRef.current = contextKey;
    }
  }, [contextKey]);

  // Focus management: focus the composer on open, return focus to the launcher
  // on close so keyboard users aren't left without a visible focus target.
  useEffect(() => {
    if (copilotOpen) {
      inputRef.current?.focus();
    } else {
      launcherRef.current?.focus?.();
    }
  }, [copilotOpen]);

  // Scroll the latest message into view as the conversation grows.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "nearest" });
  }, [thread, busy, error]);

  // Escape closes the panel; the focus effect above returns focus on close.
  useEffect(() => {
    if (!copilotOpen) return;
    function onKeyDown(event) {
      if (event.key === "Escape") setCopilotOpen(false);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [copilotOpen, setCopilotOpen]);

  // Click-outside closes the panel. The launcher is rendered separately while
  // the panel is closed; when open we must not immediately close because the
  // click that opened it may still be in flight, so we check whether the click
  // landed outside the panel (and not on the launcher).
  const handleMousedown = useCallback(
    (event) => {
      if (!copilotOpen) return;
      const panel = panelRef.current;
      const launcher = launcherRef.current;
      const target = event.target;
      if (panel && !panel.contains(target) && launcher && !launcher.contains(target)) {
        setCopilotOpen(false);
      }
    },
    [copilotOpen, setCopilotOpen]
  );

  useEffect(() => {
    if (!copilotOpen) return;
    document.addEventListener("mousedown", handleMousedown);
    return () => document.removeEventListener("mousedown", handleMousedown);
  }, [copilotOpen, handleMousedown]);

  const sendQuestion = useCallback(
    async (textToSend) => {
      const text = (textToSend || question).trim();
      if (!text || busy || !canView) return;

      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      setQuestion("");
      setError(null);
      setBusy(true);

      const newTurn = { role: "user", text };
      setThread((prev) => [...prev, newTurn]);

      // Build multi-turn history payload so follow-up questions ("show me the
      // three highest-value ones") can resolve pronouns against prior context.
      const historyPayload = thread.slice(-6).map((m) => ({
        role: m.role,
        content: m.text || m.data?.summary || m.data?.title || "",
      }));

      const payload = {
        question: text,
        reconciliation_run_id: aiContext.reconciliationRunId || undefined,
        transaction_id: aiContext.transactionId || undefined,
        match_id: aiContext.matchId || undefined,
        exception_id: aiContext.exceptionId || undefined,
        history: historyPayload.length > 0 ? historyPayload : undefined,
      };

      try {
        const answer = await askLedgerLens(payload, { signal: controller.signal });
        if (!controller.signal.aborted) {
          setThread((prev) => [...prev, { role: "assistant", data: answer }]);
        }
      } catch (err) {
        if (err?.name === "AbortError" || controller.signal.aborted) return;
        setError(err);
      } finally {
        if (!controller.signal.aborted) {
          setBusy(false);
        }
      }
    },
    [question, busy, canView, thread, aiContext]
  );

  function handleSubmit(event) {
    event?.preventDefault();
    sendQuestion(question);
  }

  const suggestions = getSuggestions(aiContext);

  return (
    <>
      {!copilotOpen && (
        <button
          ref={launcherRef}
          type="button"
          onClick={() => setCopilotOpen(true)}
          aria-label="Open Ask LedgerLens"
          aria-expanded={false}
          className="fixed bottom-5 right-5 z-40 flex h-11 items-center gap-2.5 rounded-lg border border-border bg-card px-4 text-sm font-medium text-foreground shadow-lg transition-colors hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-primary"
        >
          <span className="flex size-6 items-center justify-center rounded-md bg-primary/10 text-primary">
            <ScanSearch className="size-4" aria-hidden="true" />
          </span>
          <span className="font-semibold tracking-tight">Ask LedgerLens</span>
          {aiContext.reconciliationRunId && (
            <span className="ml-1 rounded border border-border px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">
              Run {aiContext.reconciliationRunId.slice(-6)}
            </span>
          )}
        </button>
      )}

      {copilotOpen && (
        <section
          ref={panelRef}
          aria-label="Ask LedgerLens"
          role="dialog"
          aria-modal="false"
          className="fixed bottom-0 right-0 z-50 flex h-[min(85vh,640px)] w-full max-w-md flex-col overflow-hidden border-t border-l border-border bg-background shadow-2xl sm:bottom-5 sm:right-5 sm:h-[580px] sm:rounded-xl sm:border"
        >
          {/* Header */}
          <header className="flex flex-col border-b border-border bg-sidebar text-sidebar-foreground">
            <div className="flex items-center justify-between gap-3 px-4 py-3">
              <div className="flex min-w-0 items-center gap-2.5">
                <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary">
                  <ScanSearch className="size-4" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-semibold tracking-tight">LedgerLens</h2>
                  <p className="text-[11px] text-muted-foreground">Reconciliation intelligence</p>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-0.5">
                {thread.length > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      setThread([]);
                      setError(null);
                    }}
                    title="New conversation"
                    aria-label="Start a new conversation"
                    className="flex size-7 items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary"
                  >
                    <RotateCcw className="size-3.5" aria-hidden="true" />
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setCopilotOpen(false)}
                  title="Close"
                  aria-label="Close Ask LedgerLens"
                  className="flex size-7 items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <X className="size-4" aria-hidden="true" />
                </button>
              </div>
            </div>

            {/* Context badge bar */}
            <ContextBar aiContext={aiContext} />
          </header>

          {/* Conversation */}
          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
            {thread.length === 0 && !error && (
              <EmptyState suggestions={suggestions} canView={canView} onAsk={sendQuestion} busy={busy} />
            )}

            {thread.map((message, index) => (
              <MessageRow key={index} message={message} />
            ))}

            {busy && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3.5 py-2.5 text-xs font-medium text-muted-foreground">
                  <Spinner /> Investigating LedgerLens records…
                </div>
              </div>
            )}

            {error && <ErrorState error={error} />}

            <div ref={bottomRef} />
          </div>

          {/* Composer */}
          <footer className="border-t border-border bg-background p-3">
            <form onSubmit={handleSubmit} className="flex items-end gap-2">
              <textarea
                ref={inputRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder={
                  canView
                    ? aiContext.reconciliationRunId
                      ? "Ask about this reconciliation…"
                      : "Ask about workspace reconciliation data…"
                    : "You don't have view access."
                }
                disabled={!canView || busy}
                rows={1}
                maxLength={600}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendQuestion(question);
                  }
                }}
                className="max-h-32 flex-1 resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-60"
              />
              <Button
                type="submit"
                size="sm"
                disabled={!canView || busy || !question.trim()}
                aria-label="Send question"
                className="shrink-0"
              >
                <span className="sm:hidden">
                  <CornerDownLeft className="size-4" aria-hidden="true" />
                </span>
                <span className="hidden sm:inline">Ask</span>
              </Button>
            </form>
          </footer>
        </section>
      )}
    </>
  );
}

/**
 * Welcome / starter state. Only shown while the conversation is empty. The
 * prompts are LedgerLens-specific actions, not generic help — but the composer
 * remains free-form, so they are shortcuts, not restrictions.
 */
function EmptyState({ suggestions, canView, onAsk, busy }) {
  if (!canView) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
        You don&rsquo;t have permission to view financial data in this workspace.
      </div>
    );
  }
  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm font-medium text-foreground">
          Investigate the reconciliation records in this workspace.
        </p>
        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
          Ask LedgerLens to explain match rates, unmatched transactions,
          exceptions, and engine decisions using the actual records on file —
          it never changes reconciliation state.
        </p>
      </div>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Suggested questions
        </p>
        <div className="mt-2.5 space-y-2">
          {suggestions.map((item, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => onAsk(item.prompt)}
              disabled={busy}
              className="flex w-full items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2.5 text-left text-xs font-medium text-foreground transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
            >
              <span>{item.label}</span>
              <CornerDownLeft className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function ContextBar({ aiContext }) {
  const summary = aiContext.activeRunSummary;

  if (aiContext.transactionId) {
    return (
      <div className="flex items-center justify-between gap-2 border-t border-border/60 px-4 py-2 text-xs">
        <span className="font-medium text-muted-foreground">Transaction context</span>
        <span className="font-mono text-foreground/80">{aiContext.transactionId.slice(-8)}</span>
      </div>
    );
  }

  if (aiContext.matchId) {
    return (
      <div className="flex items-center justify-between gap-2 border-t border-border/60 px-4 py-2 text-xs">
        <span className="font-medium text-muted-foreground">Match context</span>
        <span className="font-mono text-foreground/80">{aiContext.matchId.slice(-8)}</span>
      </div>
    );
  }

  if (aiContext.exceptionId) {
    return (
      <div className="flex items-center justify-between gap-2 border-t border-border/60 px-4 py-2 text-xs">
        <span className="font-medium text-muted-foreground">Exception context</span>
        <span className="font-mono text-foreground/80">{aiContext.exceptionId.slice(-8)}</span>
      </div>
    );
  }

  if (aiContext.reconciliationRunId) {
    return (
      <div className="space-y-1.5 border-t border-border/60 px-4 py-2">
        <div className="flex items-center justify-between gap-2 text-xs">
          <span className="font-medium text-muted-foreground">Active run context</span>
          <span className="font-mono text-foreground/80">{aiContext.reconciliationRunId.slice(-10)}</span>
        </div>
        {summary && (
          <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
            <span className="rounded bg-muted px-1.5 py-0.5 text-foreground/80">
              {formatCount(summary.totalTransactions ?? 0)} records
            </span>
            <span className="rounded bg-success/10 px-1.5 py-0.5 text-success">
              {formatCount(summary.matchedCount ?? 0)} matched
            </span>
            <span className="rounded bg-muted px-1.5 py-0.5 text-muted-foreground">
              {formatCount(summary.unmatchedCount ?? 0)} unmatched
            </span>
            <span className="rounded bg-destructive/10 px-1.5 py-0.5 text-destructive">
              {formatCount(summary.exceptionCount ?? 0)} exceptions
            </span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 border-t border-border/60 px-4 py-2 text-xs text-muted-foreground">
      <Badge variant="outline" className="text-[10px]">
        Workspace scope
      </Badge>
      <span className="truncate">Active workspace financial data</span>
    </div>
  );
}

function getSuggestions(aiContext) {
  if (aiContext.transactionId) {
    return [
      { label: "Why is this transaction unmatched?", prompt: "Why is this transaction unmatched?" },
      { label: "Why did this transaction match?", prompt: "Why did this transaction match?" },
      { label: "Show candidates considered for it", prompt: "Show candidate records that were considered for this transaction." },
    ];
  }

  if (aiContext.matchId) {
    return [
      { label: "Explain why these were matched", prompt: "Explain why these records were matched together." },
      { label: "Show matched and mismatched fields", prompt: "Which fields matched and which had discrepancies?" },
    ];
  }

  if (aiContext.exceptionId) {
    return [
      { label: "Explain this exception", prompt: "Explain the cause of this exception and why it was flagged." },
      { label: "Which records are affected?", prompt: "List the transactions involved in this exception." },
    ];
  }

  if (aiContext.reconciliationRunId) {
    return [
      { label: "Summarize this reconciliation", prompt: "Explain this reconciliation." },
      { label: "Explain the unmatched transactions", prompt: "Why are so many transactions unmatched in this reconciliation?" },
      { label: "Which exceptions need attention?", prompt: "Which exceptions should I review first?" },
      { label: "Find the highest-value unmatched records", prompt: "Which unmatched transactions have the highest amounts?" },
    ];
  }

  return [
    { label: "Which reconciliation has the lowest match rate?", prompt: "Which reconciliation run has the lowest match rate?" },
    { label: "Summarize the latest reconciliation", prompt: "Summarize the latest reconciliation run in this workspace." },
    { label: "Which exceptions need attention?", prompt: "Which exceptions should I investigate first across the workspace?" },
    { label: "Show the biggest unresolved issues", prompt: "What are the biggest unresolved reconciliation issues in this workspace?" },
  ];
}

function MessageRow({ message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-xl rounded-br-sm bg-foreground px-3.5 py-2.5 text-xs font-medium leading-relaxed text-background">
          {message.text}
        </p>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[95%] rounded-xl rounded-bl-sm border border-border bg-card p-3.5">
        <AiAnswer
          data={message.data}
          emptyMessage="There isn't enough reconciliation evidence available to answer this."
        />
      </div>
    </div>
  );
}
