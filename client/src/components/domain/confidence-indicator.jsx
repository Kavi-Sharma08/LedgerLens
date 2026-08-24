import { cn } from "@/lib/utils";
import { formatPercent } from "@/lib/format";

/**
 * Confidence meter for match decisions. The percentage comes straight from
 * the engine's stored confidence — the frontend never computes scores.
 */
export function ConfidenceIndicator({ confidence, className, showLabel = true }) {
  const value = Number(confidence);
  if (!Number.isFinite(value)) return <span className="text-sm text-muted-foreground">—</span>;

  const clamped = Math.min(1, Math.max(0, value));
  const tone =
    clamped >= 0.9
      ? "bg-success"
      : clamped >= 0.7
        ? "bg-info"
        : "bg-warning";

  return (
    <span className={cn("inline-flex min-w-28 items-center gap-2", className)}>
      <span
        role="meter"
        aria-valuenow={Math.round(clamped * 100)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Confidence ${Math.round(clamped * 100)} percent`}
        className="h-1.5 w-16 overflow-hidden rounded-full bg-muted"
      >
        <span className={cn("block h-full rounded-full", tone)} style={{ width: `${clamped * 100}%` }} />
      </span>
      {showLabel && (
        <span className="text-xs font-medium tabular-nums text-foreground">
          {formatPercent(clamped)}
        </span>
      )}
    </span>
  );
}
