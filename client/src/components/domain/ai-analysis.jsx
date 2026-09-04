"use client";

import { useCallback, useRef, useState } from "react";
import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboard } from "@/components/common/dashboard-context";
import {
  AIResponse,
  AIFindings,
  AIEvidenceCards,
  AICauseList,
  AILimitations,
} from "@/components/domain/ai-response";

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
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner />
        <span>Analyzing reconciliation...</span>
      </div>
      <Skeleton className="h-16 w-full rounded-lg" />
      <Skeleton className="h-20 w-full rounded-lg" />
    </div>
  );
}

export function ErrorState({ error }) {
  const status = error?.status;
  const code = error?.code;

  let title = "Unable to complete the analysis";
  let message = "Please try again.";

  if (code === "ai_unavailable" || status === 503) {
    title = "AI service unavailable";
    message = "The AI service is temporarily unreachable. Please try again shortly.";
  } else if (code === "tool_execution_failed") {
    title = "Data retrieval failed";
    message = "Could not retrieve the data needed for analysis. Please try again.";
  } else if (code === "no_answer") {
    title = "No analysis generated";
    message = "The AI did not produce a complete answer. Please try again.";
  } else if (code === "request_too_large") {
    title = "Data too large";
    message = "This record is too large to analyze in one request.";
  } else if (status === 404) {
    title = "Record not found";
    message = "This record could not be found in the active workspace.";
  } else if (status === 403) {
    title = "Access restricted";
    message = "You don't have permission to analyze financial data in this workspace.";
  } else if (code === "rate_limited" || status === 429) {
    title = "Too many requests";
    message = "Please wait a moment and try again.";
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
  const findings = data?.findings || [];
  const evidence = data?.evidence || [];

  return (
    <AIResponse data={data} emptyMessage={emptyMessage}>
      <AIFindings findings={findings} />
      <AIEvidenceCards evidence={evidence} />
      <AICauseList title="Likely causes" items={data?.likely_causes} />
      <AICauseList title="Recommendations" items={data?.recommendations} />
      <AILimitations items={data?.limitations} />
    </AIResponse>
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
