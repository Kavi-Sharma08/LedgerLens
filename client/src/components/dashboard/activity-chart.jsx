"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

/**
 * Placeholder reconciliation activity chart.
 * Pure markup (no chart library yet) — the data shape matches what FastAPI
 * will return so the swap is a data change, not a component rewrite.
 */
export function ActivityChart({ activity }) {
  const max = Math.max(...activity.map((point) => point.matched + point.exceptions));

  return (
    <Card className="min-w-0">
      <CardHeader className="flex-row items-center justify-between space-y-0">
        <div className="space-y-1">
          <CardTitle>Reconciliation activity</CardTitle>
          <CardDescription>Matched vs. exceptions per month</CardDescription>
        </div>
        <Badge variant="outline">Placeholder data</Badge>
      </CardHeader>
      <CardContent>
        <div role="img" aria-label="Bar chart of matched transactions and exceptions per month" className="flex h-44 items-end gap-3 sm:gap-5">
          {activity.map((point) => {
            const matchedHeight = (point.matched / max) * 100;
            const exceptionHeight = (point.exceptions / max) * 100;
            return (
              <div key={point.label} className="flex h-full flex-1 flex-col items-center justify-end gap-1.5">
                <div className="flex w-full max-w-8 flex-col justify-end" style={{ height: "100%" }}>
                  <div
                    className="w-full rounded-t-[4px] bg-warning/70"
                    style={{ height: `${exceptionHeight}%` }}
                    title={`${point.exceptions} exceptions`}
                  />
                  <div
                    className="w-full rounded-b-[2px] bg-primary"
                    style={{ height: `${matchedHeight}%` }}
                    title={`${point.matched}% matched`}
                  />
                </div>
                <span className="text-[11px] text-muted-foreground">{point.label}</span>
              </div>
            );
          })}
        </div>
        <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span aria-hidden="true" className="size-2 rounded-[3px] bg-primary" /> Matched
          </span>
          <span className="flex items-center gap-1.5">
            <span aria-hidden="true" className="size-2 rounded-[3px] bg-warning/70" /> Exceptions
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
