"use client";

import { useEffect } from "react";
import { RotateCcw, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Route-level error boundary for authenticated areas.
 * Distinguishes "API unreachable" from unknown failures and offers recovery.
 */
export default function DashboardError({ error, reset }) {
  useEffect(() => {
    console.error("Dashboard error:", error);
  }, [error]);

  const isNetworkIssue =
    error?.message?.includes("reach the LedgerLens servers") ||
    error?.message?.includes("temporarily unable");

  return (
    <div className="mx-auto flex w-full max-w-lg flex-col items-center px-4 py-24 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-destructive/10">
        <TriangleAlert className="size-6 text-destructive" aria-hidden="true" />
      </span>
      <h1 className="mt-5 text-xl font-semibold tracking-tight text-foreground">
        {isNetworkIssue ? "We can't reach LedgerLens right now" : "Something went wrong"}
      </h1>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        {isNetworkIssue
          ? "Your data is safe. We're having trouble connecting to LedgerLens services — check your connection and try again."
          : error?.message || "An unexpected error occurred while loading this page."}
      </p>
      <div className="mt-6 flex gap-3">
        <Button onClick={reset}>
          <RotateCcw aria-hidden="true" />
          Try again
        </Button>
        <Button variant="outline" render={<a href="/dashboard" />}>
          Back to overview
        </Button>
      </div>
    </div>
  );
}
