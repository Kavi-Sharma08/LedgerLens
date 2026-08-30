"use client";

import { useCallback, useRef, useState } from "react";
import { Sparkles, ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboard } from "@/components/common/dashboard-context";
import { useAiContext } from "@/components/common/ai-context";
import { cn } from "@/lib/utils";

/**
 * AI Reconciliation Intelligence panel.
 * Reusable across transactions, matches, exceptions, and reconciliation runs.
 */

const KIND_META = {
  fact: { label: "Fact", className: "border-info/25 bg-info/5 text-info" },
  inference: { label: "Inference", className: "border-border bg-muted/30 text-muted-foreground" },
  recommendation: { label: "Recommendation", className: "border-primary/25 bg-primary/5 text-primary" },
};

const CONFIDENCE_META = {
  high: { label: "High confidence", className: "bg-success/10 text-success" },
  medium: { label: "Medium confidence", className: "bg-info/10 text-info" },
  low: { label: "Low confidence", className: "bg-warning/10 text-warning" },
};

export function AiAnalysis({ analyze, label = "Analyze reconciliation", disabled }) {
  const { can } = useDashboard();
  const [state, setState] = useState({ status: "idle" });
  const controllerRef = useRef(null);

  const canView = Boolean(can.viewData);

  const run = useCallback(async () => {
    if (controllerRef.current) controllerRef.current.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setState({ status: "loading" });
    try {
      const result = await analyze({ signal: controller.signal });
      if (!controller.signal.aborted) setState({ status: "success", data: result });
    } catch (err) {
      if (err?.name === "AbortError" || controller.signal.aborted) return;
      setState({ status: "error", error: err });
    }
  }, [analyze]);

  return (
    <section aria-label={label}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
          Reconciliation analysis
        </h3>
        {state.status === "success" ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={run}
            disabled={disabled && Boolean(state.data?.title === "Analysis unavailable")}
          >
            <Sparkles className="mr-1.5 size-3.5" aria-hidden="true" />
            Re-analyze
          </Button>
        ) : (
          <Button
            variant="outline"
            size="sm"
            onClick={run}
            disabled={!canView || disabled || state.status === "loading"}
          >
            {state.status === "loading" ? (
              <>
                <Spinner />
                Analyzing…
              </>
            ) : (
              <>
                <Sparkles className="mr-1.5 size-3.5" aria-hidden="true" />
                {state.status === "error" ? "Retry" : label}
              </>
            )}
          </Button>
        )}
      </div>

      <div className="mt-3">
        {state.status === "idle" && (
          <p className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-4 text-sm text-muted-foreground">
            Investigate this reconciliation result using the workspace&rsquo;s actual financial records.
          </p>
        )}
        {state.status === "loading" && <LoadingState />}
        {state.status === "error" && <ErrorState error={state.error} />}
        {state.status === "success" && (
          <SuccessState data={state.data} unavailable={!state.data?.title || state.data?.title === "Analysis unavailable"} />
        )}
        {!canView && state.status === "idle" && (
          <p className="mt-2 text-xs text-muted-foreground">
            You don&rsquo;t have permission to view financial data.
          </p>
        )}
      </div>
    </section>
  );
}

function LoadingState() {
  return (
    <div aria-busy="true" aria-label="Analyzing reconciliation" className="space-y-3 rounded-lg border border-border bg-card p-4">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-16 w-full rounded-lg" />
      <Skeleton className="h-20 w-full rounded-lg" />
    </div>
  );
}

export function ErrorState({ error }) {
  const status = error?.status;
  const code = error?.code;

  let title = "Reconciliation analysis failed";
  let message =
    error?.message ||
    "LedgerLens could not complete the reconciliation analysis right now.";

  if (code === "ai_unavailable" || status === 503) {
    title = "AI service unavailable";
    message = "LedgerLens AI is temporarily unreachable. Please try again shortly.";
  } else if (code === "tool_execution_failed") {
    title = "Data retrieval failed";
    message =
      "LedgerLens could not retrieve the reconciliation data from this workspace.";
  } else if (code === "no_answer") {
    title = "No analysis generated";
    message =
      "The AI did not produce a complete answer. Try rephrasing your question.";
  } else if (status === 404) {
    title = "Record not found";
    message =
      "This reconciliation or record could not be found in the active workspace.";
  } else if (status === 403) {
    title = "Access restricted";
    message =
      "You don't have permission to analyze financial data in this workspace.";
  }

  return (
    <div role="alert" className="rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-4">
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{message}</p>
    </div>
  );
}

function SuccessState({ data, unavailable }) {
  if (unavailable || !data?.summary) {
    return (
      <p className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-4 text-sm text-muted-foreground">
        There isn&rsquo;t enough reconciliation evidence available to explain this record.
      </p>
    );
  }
  return <AiAnswer data={data} />;
}

export function AiAnswer({ data, emptyMessage }) {
  const { setNavigationTarget } = useAiContext();

  if (!data?.summary) {
    return (
      <p className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-4 text-sm text-muted-foreground">
        {emptyMessage ||
          "There isn't enough reconciliation evidence available to explain this record."}
      </p>
    );
  }

  const findings = data.findings || [];
  const evidence = data.evidence || [];

  return (
    <div className="space-y-4">
      {data.title && (
        <div>
          <p className="text-base font-semibold tracking-tight text-foreground">{data.title}</p>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{data.summary}</p>
        </div>
      )}

      {data.confidence && CONFIDENCE_META[data.confidence] && (
        <div className="flex items-center gap-2">
          <Badge className={CONFIDENCE_META[data.confidence].className}>
            {CONFIDENCE_META[data.confidence].label}
          </Badge>
        </div>
      )}

      {findings.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Key Findings &amp; Analysis
          </p>
          <ul role="list" className="space-y-2">
            {findings.map((finding, index) => {
              const meta = KIND_META[finding.kind];
              const showBadge = meta && finding.kind !== "inference";
              return (
                <li key={index} className="flex items-start gap-2 rounded-lg border border-border/60 bg-muted/15 px-3 py-2 text-xs leading-relaxed text-foreground">
                  {showBadge && (
                    <Badge className={cn("shrink-0 mt-0.5 font-normal text-[10px]", meta.className)}>
                      {meta.label}
                    </Badge>
                  )}
                  <span className="flex-1">{finding.text}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {evidence.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Reconciliation evidence
          </p>
          <dl className="mt-2 grid gap-2 sm:grid-cols-2">
            {evidence.map((item, index) => {
              const entityType = item.entity_type || item.entityType;
              const entityId = item.entity_id || item.entityId;

              return (
                <div key={index} className="flex flex-col justify-between rounded-lg border border-border bg-card px-3 py-2.5">
                  <div>
                    <dt className="text-xs font-medium text-muted-foreground">{item.label}</dt>
                    <dd className="mt-0.5 text-sm font-semibold text-foreground">{item.value}</dd>
                    {item.source && <dd className="mt-0.5 text-[11px] text-muted-foreground/70">{item.source}</dd>}
                  </div>
                  {entityType && entityId && (
                    <div className="mt-2 border-t border-border/50 pt-1.5">
                      <Button
                        variant="ghost"
                        size="xs"
                        onClick={() => setNavigationTarget?.({ type: entityType, id: entityId })}
                        className="h-6 gap-1 px-1.5 text-xs text-primary hover:text-primary"
                      >
                        <span>View {entityType}</span>
                        <ExternalLink className="size-3" />
                      </Button>
                    </div>
                  )}
                </div>
              );
            })}
          </dl>
        </div>
      )}

      {data.likely_causes?.length > 0 && (
        <CauseList title="Likely causes" items={data.likely_causes} />
      )}

      {data.recommendations?.length > 0 && (
        <CauseList title="Recommendations" items={data.recommendations} />
      )}

      {data.limitations?.length > 0 && (
        <p className="text-xs leading-relaxed text-muted-foreground">
          <span className="font-medium">Limitations:</span>{" "}
          {data.limitations.join(" ")}
        </p>
      )}
    </div>
  );
}

function CauseList({ title, items }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</p>
      <ul role="list" className="mt-2 space-y-1.5">
        {items.map((item, index) => (
          <li key={index} className="flex items-start gap-2 text-sm text-muted-foreground">
            <span aria-hidden="true" className="mt-[7px] size-1 shrink-0 rounded-full bg-muted-foreground/60" />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AiResponseUnavailable({ data }) {
  return <SuccessState data={data} unavailable />;
}

export function Spinner() {
  return (
    <span
      aria-hidden="true"
      className="mr-1.5 inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
    />
  );
}
