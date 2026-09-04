"use client";

import { ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAiContext } from "@/components/common/ai-context";

const CONFIDENCE_META = {
  high: { label: "High confidence", className: "bg-success/10 text-success" },
  medium: { label: "Medium confidence", className: "bg-info/10 text-info" },
  low: { label: "Low confidence", className: "bg-warning/10 text-warning" },
};

export function AIConfidenceBadge({ confidence }) {
  if (!confidence || !CONFIDENCE_META[confidence]) return null;
  const meta = CONFIDENCE_META[confidence];
  return <Badge className={meta.className}>{meta.label}</Badge>;
}

export function AIFindings({ findings = [] }) {
  if (findings.length === 0) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Key findings
      </p>
      <ul role="list" className="space-y-2">
        {findings.map((finding, index) => {
          return (
            <li
              key={index}
              className="flex items-start gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm leading-relaxed text-foreground"
            >
              <span className="mt-0.5 shrink-0 text-success">&#10003;</span>
              <span className="flex-1 min-w-0 overflow-wrap-anywhere">{finding.text}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function AIEvidenceCards({ evidence = [] }) {
  const { setNavigationTarget } = useAiContext();

  if (evidence.length === 0) return null;

  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Evidence
      </p>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {evidence.map((item, index) => {
          const entityType = item.entity_type || item.entityType;
          const entityId = item.entity_id || item.entityId;

          return (
            <div
              key={index}
              className="flex flex-col justify-between rounded-lg border border-border bg-card px-3 py-2.5 min-w-0"
            >
              <div className="min-w-0">
                <dt className="text-xs font-medium text-muted-foreground truncate">
                  {item.label}
                </dt>
                <dd className="mt-0.5 text-sm font-semibold text-foreground break-words overflow-wrap-anywhere">
                  {item.value}
                </dd>
                {item.source && (
                  <dd className="mt-0.5 text-[11px] text-muted-foreground/70 truncate">
                    {item.source}
                  </dd>
                )}
              </div>
              {entityType && entityId && (
                <div className="mt-2 border-t border-border/50 pt-1.5">
                  <Button
                    variant="ghost"
                    size="xs"
                    onClick={() =>
                      setNavigationTarget?.({ type: entityType, id: entityId })
                    }
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
      </div>
    </div>
  );
}

export function AICauseList({ title, items = [] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </p>
      <ul role="list" className="mt-2 space-y-1.5">
        {items.map((item, index) => (
          <li
            key={index}
            className="flex items-start gap-2 text-sm text-muted-foreground"
          >
            <span
              aria-hidden="true"
              className="mt-[7px] size-1 shrink-0 rounded-full bg-muted-foreground/60"
            />
            <span className="min-w-0 break-words overflow-wrap-anywhere">
              {item}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AILimitations({ items = [] }) {
  if (items.length === 0) return null;
  return (
    <p className="text-xs leading-relaxed text-muted-foreground">
      <span className="font-medium">Limitations:</span>{" "}
      {items.join(" ")}
    </p>
  );
}

export function AIResponse({ data, children, emptyMessage }) {
  if (!data?.summary) {
    return (
      <p className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-4 text-sm text-muted-foreground">
        {emptyMessage ||
          "There isn't enough reconciliation evidence available to explain this record."}
      </p>
    );
  }

  return (
    <div className="space-y-4 min-w-0">
      {data.title && (
        <div>
          <p className="text-base font-semibold tracking-tight text-foreground">
            {data.title}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
            {data.summary}
          </p>
        </div>
      )}

      <AIConfidenceBadge confidence={data.confidence} />

      {children}
    </div>
  );
}
