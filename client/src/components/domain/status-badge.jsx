import { Check, CircleAlert, CircleDashed, HelpCircle, OctagonAlert, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * Single source of truth for reconciliation status semantics across the UI:
 * color + icon + human label. Color is never the only signal — every status
 * carries a distinct icon and text.
 */

const RECONCILIATION_STATUSES = {
  MATCHED: { label: "Matched", variant: "success", icon: Check },
  LIKELY_MATCH: { label: "Likely match", variant: "info", icon: Search },
  AMBIGUOUS: { label: "Needs review", variant: "warning", icon: HelpCircle },
  UNMATCHED: { label: "Unmatched", variant: "outline", icon: CircleDashed },
  EXCEPTION: { label: "Exception", variant: "destructive", icon: OctagonAlert },
  MANUAL_MATCHED: { label: "Manually matched", variant: "success", icon: Check },
};

const RUN_STATUSES = {
  QUEUED: { label: "Queued", variant: "outline", icon: CircleDashed },
  RUNNING: { label: "Running", variant: "primary", icon: CircleDashed },
  COMPLETED: { label: "Completed", variant: "success", icon: Check },
  PARTIAL: { label: "Completed with issues", variant: "warning", icon: CircleAlert },
  FAILED: { label: "Failed", variant: "destructive", icon: OctagonAlert },
};

const FILE_STATUSES = {
  UPLOADED: { label: "Uploaded", variant: "outline", icon: CircleDashed },
  PROCESSING: { label: "Processing", variant: "primary", icon: CircleDashed },
  PROCESSED: { label: "Processed", variant: "success", icon: Check },
  PARTIAL: { label: "Processed with errors", variant: "warning", icon: CircleAlert },
  FAILED: { label: "Failed", variant: "destructive", icon: OctagonAlert },
  DUPLICATE: { label: "Duplicate", variant: "neutral", icon: CopyIcon },
};

function CopyIcon({ className }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </svg>
  );
}

const EXCEPTION_STATUSES = {
  OPEN: { label: "Open", variant: "warning", icon: CircleAlert },
  INVESTIGATING: { label: "Investigating", variant: "info", icon: Search },
  RESOLVED: { label: "Resolved", variant: "success", icon: Check },
  DISMISSED: { label: "Dismissed", variant: "neutral", icon: CircleDashed },
};

const KIND_CONFIG = {
  reconciliation: RECONCILIATION_STATUSES,
  run: RUN_STATUSES,
  file: FILE_STATUSES,
  exception: EXCEPTION_STATUSES,
};

export function StatusBadge({ kind = "reconciliation", value, className }) {
  const config = KIND_CONFIG[kind]?.[value] ?? {
    label: humanize(value),
    variant: "outline",
    icon: CircleDashed,
  };
  const Icon = config.icon;
  return (
    <Badge variant={config.variant} className={cn("gap-1 font-medium", className)}>
      <Icon className="size-3" aria-hidden="true" />
      {config.label}
    </Badge>
  );
}

export function humanize(value) {
  if (!value) return "—";
  return String(value)
    .toLowerCase()
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

/** Exception reason codes -> short user-facing issue labels. */
const REASON_LABELS = {
  POSSIBLE_FEE: "Possible fee difference",
  STATUS_CONFLICT: "Status conflict",
  UNSUPPORTED_CURRENCY: "Currency mismatch",
  ZERO_AMOUNT: "Zero amount",
  FAILED_TRANSACTION: "Failed transaction",
  CANDIDATE_COLLISION: "Conflicting records",
  NEEDS_REVIEW: "Needs review",
};

export function exceptionReasonLabel(reasonCode) {
  return REASON_LABELS[reasonCode] ?? humanize(reasonCode);
}
