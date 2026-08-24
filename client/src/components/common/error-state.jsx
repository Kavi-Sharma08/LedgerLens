import { RotateCcw, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Inline error state for data fetch failures. Never renders raw backend
 * errors — callers pass an already user-friendly message (ApiError.message).
 */
export function ErrorState({ title = "Something went wrong", message, onRetry, className }) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-border bg-card px-6 py-10 text-center",
        className
      )}
    >
      <span className="flex size-10 items-center justify-center rounded-full bg-destructive/10">
        <TriangleAlert className="size-5 text-destructive" aria-hidden="true" />
      </span>
      <h3 className="mt-4 text-sm font-semibold text-foreground">{title}</h3>
      {message && (
        <p className="mt-1 max-w-sm text-sm leading-relaxed text-muted-foreground">{message}</p>
      )}
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-5" onClick={onRetry}>
          <RotateCcw aria-hidden="true" />
          Try again
        </Button>
      )}
    </div>
  );
}
