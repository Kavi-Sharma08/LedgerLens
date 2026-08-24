import { Check, Minus, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { humanize } from "@/components/domain/status-badge";

/**
 * Renders the engine's per-signal score breakdown as evidence chips.
 * Data arrives verbatim from the backend (scoreBreakdown, matchedFields,
 * mismatchedFields) — this component never derives or rescores anything.
 *
 * scoreBreakdown: { amountScore: "1.0000", dateScore: "0.9000", ... }
 */
const SIGNALS = [
  { key: "amountScore", label: "Amount" },
  { key: "dateScore", label: "Date" },
  { key: "referenceScore", label: "Reference" },
  { key: "counterpartyScore", label: "Counterparty" },
  { key: "descriptionScore", label: "Description" },
];

export function EvidenceList({ scoreBreakdown = {}, reasons = [], className }) {
  const available = SIGNALS.filter((signal) => scoreBreakdown[signal.key] != null);

  return (
    <div className={cn("space-y-3", className)}>
      {available.length > 0 && (
        <ul role="list" className="grid gap-2 sm:grid-cols-2">
          {available.map((signal) => {
            const raw = Number(scoreBreakdown[signal.key]);
            const score = Number.isFinite(raw) ? raw : null;
            const state =
              score == null ? "missing" : score >= 0.99 ? "match" : score >= 0.5 ? "partial" : "mismatch";
            return (
              <li
                key={signal.key}
                className={cn(
                  "flex items-center justify-between gap-2 rounded-lg border px-3 py-2",
                  state === "match" && "border-success/25 bg-success/5",
                  state === "partial" && "border-border bg-muted/30",
                  state === "mismatch" && "border-destructive/20 bg-destructive/5"
                )}
              >
                <span className="flex items-center gap-2 text-sm text-foreground">
                  <SignalIcon state={state} />
                  {signal.label}
                </span>
                {score != null && (
                  <Badge variant={state === "match" ? "success" : state === "mismatch" ? "destructive" : "outline"}>
                    {(score * 100).toFixed(0)}%
                  </Badge>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {reasons.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Why this decision
          </p>
          <ul role="list" className="mt-2 space-y-1.5">
            {reasons.map((reason) => (
              <li key={reason} className="flex items-start gap-2 text-sm text-muted-foreground">
                <span aria-hidden="true" className="mt-[7px] size-1 shrink-0 rounded-full bg-muted-foreground/60" />
                {humanize(reason)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function SignalIcon({ state }) {
  if (state === "match") {
    return (
      <span className="flex size-4.5 items-center justify-center rounded-full bg-success/15">
        <Check className="size-3 text-success" aria-hidden="true" />
      </span>
    );
  }
  if (state === "mismatch") {
    return (
      <span className="flex size-4.5 items-center justify-center rounded-full bg-destructive/10">
        <X className="size-3 text-destructive" aria-hidden="true" />
      </span>
    );
  }
  return (
    <span className="flex size-4.5 items-center justify-center rounded-full bg-muted">
      <Minus className="size-3 text-muted-foreground" aria-hidden="true" />
    </span>
  );
}
