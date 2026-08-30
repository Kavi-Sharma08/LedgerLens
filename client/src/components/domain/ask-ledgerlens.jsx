"use client";

import { useEffect, useRef, useState } from "react";
import { Sparkles, X, RotateCcw, Bot, ShieldCheck, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AiAnswer, Spinner, ErrorState } from "@/components/domain/ai-analysis";
import { useDashboard } from "@/components/common/dashboard-context";
import { useAiContext } from "@/components/common/ai-context";
import { askLedgerLens } from "@/lib/api/ai";
import { formatCount } from "@/lib/format";

/**
 * LedgerLens Reconciliation Copilot — Finance Controller assistant for
 * investigating reconciliation evidence, unmatched exceptions, and engine decisions.
 */
export function AskLedgerLens() {
  const { can } = useDashboard();
  const { aiContext, copilotOpen, setCopilotOpen } = useAiContext();
  const [question, setQuestion] = useState("");
  const [thread, setThread] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const inputRef = useRef(null);
  const bottomRef = useRef(null);

  const canView = Boolean(can.viewData);

  // Auto-reset conversation when active context changes (prevents cross-entity context bleed)
  const contextKey = `${aiContext.reconciliationRunId || ""}:${aiContext.transactionId || ""}:${aiContext.matchId || ""}:${aiContext.exceptionId || ""}`;
  const prevKeyRef = useRef(contextKey);

  useEffect(() => {
    if (prevKeyRef.current !== contextKey) {
      setThread([]);
      setError(null);
      prevKeyRef.current = contextKey;
    }
  }, [contextKey]);

  useEffect(() => {
    if (copilotOpen) {
      inputRef.current?.focus();
    }
  }, [copilotOpen]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "nearest" });
  }, [thread, busy, error]);

  const abortControllerRef = useRef(null);

  async function sendQuestion(textToSend) {
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

    // Build multi-turn history payload
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
  }


  function handleSubmit(event) {
    event?.preventDefault();
    sendQuestion(question);
  }

  const suggestions = getSuggestions(aiContext);

  return (
    <>
      {!copilotOpen && (
        <button
          type="button"
          onClick={() => setCopilotOpen(true)}
          aria-label="Open Reconciliation Copilot"
          className="fixed bottom-5 right-5 z-40 flex h-12 items-center gap-2.5 rounded-full bg-sidebar px-4.5 py-2.5 text-sm font-medium text-white shadow-xl transition-all duration-200 hover:scale-105 hover:bg-sidebar/90 hover:shadow-2xl focus-visible:ring-2 focus-visible:ring-primary"
        >
          <div className="flex size-6 items-center justify-center rounded-full bg-primary/20 text-primary">
            <Sparkles className="size-3.5" aria-hidden="true" />
          </div>
          <span className="font-semibold tracking-tight">Reconciliation Copilot</span>
          {aiContext.reconciliationRunId && (
            <span className="ml-1 rounded bg-white/10 px-1.5 py-0.5 font-mono text-[11px] text-white/80">
              Run {aiContext.reconciliationRunId.slice(-6)}
            </span>
          )}
        </button>
      )}

      {copilotOpen && (
        <section
          aria-label="LedgerLens Reconciliation Copilot"
          className="fixed bottom-0 right-0 z-50 flex h-[min(85vh,640px)] w-full max-w-lg flex-col border-t border-l border-border bg-background shadow-2xl sm:bottom-5 sm:right-5 sm:h-[580px] sm:rounded-2xl sm:border"
        >
          {/* Header */}
          <header className="flex flex-col border-b border-border bg-sidebar px-4 py-3 text-white sm:rounded-t-2xl">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <div className="flex size-7 items-center justify-center rounded-lg bg-primary/20 text-primary">
                  <Bot className="size-4" aria-hidden="true" />
                </div>
                <div>
                  <h2 className="text-sm font-semibold tracking-tight text-white">Reconciliation Copilot</h2>
                  <p className="text-[11px] text-white/70">Investigation &amp; Explanation Layer</p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {thread.length > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      setThread([]);
                      setError(null);
                    }}
                    title="Reset conversation"
                    aria-label="Reset conversation"
                    className="flex size-7 items-center justify-center rounded-md text-white/70 outline-none hover:bg-white/10 hover:text-white"
                  >
                    <RotateCcw className="size-3.5" aria-hidden="true" />
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setCopilotOpen(false)}
                  aria-label="Close Copilot"
                  className="flex size-7 items-center justify-center rounded-md text-white/70 outline-none hover:bg-white/10 hover:text-white"
                >
                  <X className="size-4" aria-hidden="true" />
                </button>
              </div>
            </div>

            {/* Context Badge Bar */}
            <ContextBar aiContext={aiContext} />
          </header>

          {/* Main Thread Content */}
          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
            {thread.length === 0 && !error && (
              <div className="space-y-4">
                <div className="rounded-xl border border-border bg-card p-4">
                  <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
                    <ShieldCheck className="size-4 text-success" />
                    <span>Evidence-Backed Finance Intelligence</span>
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
                    Investigate actual workspace records. Answers are strictly grounded in LedgerLens engine evidence and never alter reconciliation state.
                  </p>
                </div>

                {/* Suggested Action Pills */}
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Suggested investigations
                  </p>
                  <div className="mt-2.5 space-y-2">
                    {suggestions.map((item, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => sendQuestion(item.prompt)}
                        disabled={!canView || busy}
                        className="flex w-full items-center justify-between rounded-lg border border-border bg-card px-3 py-2.5 text-left text-xs font-medium text-foreground transition-colors hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50"
                      >
                        <span>{item.label}</span>
                        <ChevronRight className="size-3.5 text-muted-foreground shrink-0" />
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {thread.map((message, index) => (
              <MessageRow key={index} message={message} />
            ))}

            {busy && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-xl rounded-bl-sm border border-border bg-card px-3.5 py-2.5 text-xs font-medium text-muted-foreground">
                  <Spinner /> Analyzing reconciliation evidence…
                </div>
              </div>
            )}

            {error && <ErrorState error={error} />}

            <div ref={bottomRef} />
          </div>

          {/* Footer Input */}
          <footer className="border-t border-border bg-background p-3">
            <form onSubmit={handleSubmit} className="flex gap-2">
              <input
                ref={inputRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder={
                  canView
                    ? aiContext.reconciliationRunId
                      ? "Ask about this reconciliation run..."
                      : "Ask about workspace reconciliation data..."
                    : "You don't have view access."
                }
                disabled={!canView || busy}
                maxLength={600}
                className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-60"
              />
              <Button type="submit" size="sm" disabled={!canView || busy || !question.trim()}>
                Ask
              </Button>
            </form>
          </footer>
        </section>
      )}
    </>
  );
}

function ContextBar({ aiContext }) {
  const summary = aiContext.activeRunSummary;

  if (aiContext.transactionId) {
    return (
      <div className="mt-2.5 flex items-center justify-between rounded-lg bg-white/10 px-3 py-1.5 text-xs">
        <span className="font-medium text-white/80">Transaction Context</span>
        <span className="font-mono text-white/90">{aiContext.transactionId.slice(-8)}</span>
      </div>
    );
  }

  if (aiContext.matchId) {
    return (
      <div className="mt-2.5 flex items-center justify-between rounded-lg bg-white/10 px-3 py-1.5 text-xs">
        <span className="font-medium text-white/80">Match Decision Context</span>
        <span className="font-mono text-white/90">{aiContext.matchId.slice(-8)}</span>
      </div>
    );
  }

  if (aiContext.exceptionId) {
    return (
      <div className="mt-2.5 flex items-center justify-between rounded-lg bg-white/10 px-3 py-1.5 text-xs">
        <span className="font-medium text-white/80">Exception Context</span>
        <span className="font-mono text-white/90">{aiContext.exceptionId.slice(-8)}</span>
      </div>
    );
  }

  if (aiContext.reconciliationRunId) {
    return (
      <div className="mt-2.5 space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="font-medium text-white/80">Active Run Context</span>
          <span className="font-mono text-white/90">{aiContext.reconciliationRunId.slice(-10)}</span>
        </div>
        {summary && (
          <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px] text-white/90">
            <span className="rounded bg-white/10 px-1.5 py-0.5">{formatCount(summary.totalTransactions ?? 0)} records</span>
            <span className="rounded bg-success/20 px-1.5 py-0.5 text-success-foreground">{formatCount(summary.matchedCount ?? 0)} matched</span>
            <span className="rounded bg-white/10 px-1.5 py-0.5">{formatCount(summary.unmatchedCount ?? 0)} unmatched</span>
            <span className="rounded bg-destructive/20 px-1.5 py-0.5 text-destructive-foreground">{formatCount(summary.exceptionCount ?? 0)} exceptions</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="mt-2.5 flex items-center gap-1.5 text-xs text-white/70">
      <Badge variant="outline" className="border-white/20 text-white/90 text-[10px]">
        Workspace Scope
      </Badge>
      <span>Active workspace financial data</span>
    </div>
  );
}

function getSuggestions(aiContext) {
  if (aiContext.transactionId) {
    return [
      { label: "Why is this transaction unmatched?", prompt: "Why is this transaction unmatched?" },
      { label: "Why did this transaction match?", prompt: "Why did this transaction match?" },
      { label: "Show match candidates for this transaction", prompt: "Show candidate records that were considered for this transaction." },
    ];
  }

  if (aiContext.matchId) {
    return [
      { label: "Explain why this match was formed", prompt: "Explain why these records were matched together." },
      { label: "Show matched and mismatched fields", prompt: "Which fields matched and which had discrepancies?" },
    ];
  }

  if (aiContext.exceptionId) {
    return [
      { label: "Explain exception cause & severity", prompt: "Explain the cause of this exception and why it was flagged." },
      { label: "Which transactions are affected?", prompt: "List the transactions involved in this exception." },
    ];
  }

  if (aiContext.reconciliationRunId) {
    return [
      { label: "Explain this reconciliation", prompt: "Explain this reconciliation." },
      { label: "Why are so many transactions unmatched?", prompt: "Why are so many transactions unmatched in this reconciliation?" },
      { label: "Which exceptions should I review first?", prompt: "Which exceptions should I review first?" },
      { label: "Show largest unmatched transactions", prompt: "Which unmatched transactions have the highest amounts?" },
    ];
  }

  return [
    { label: "Summarize recent reconciliations", prompt: "Summarize recent reconciliation runs in this workspace." },
    { label: "Find open exceptions needing review", prompt: "Which exceptions should I investigate first across the workspace?" },
  ];
}

function MessageRow({ message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-xs bg-foreground px-3.5 py-2.5 text-xs font-medium leading-relaxed text-background">
          {message.text}
        </p>
      </div>
    );
  }
  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[95%] rounded-2xl rounded-bl-xs border border-border bg-card p-3.5 shadow-sm">
        <AiAnswer data={message.data} emptyMessage="There isn't enough reconciliation evidence available to explain this record." />
      </div>
    </div>
  );
}
