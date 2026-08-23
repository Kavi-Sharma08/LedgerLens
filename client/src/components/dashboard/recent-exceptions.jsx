"use client";

import Link from "next/link";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/empty-state";
import { TriangleAlert } from "lucide-react";

const severityVariants = {
  warning: "warning",
  danger: "destructive",
  info: "info",
};

const statusVariants = {
  Investigating: "primary",
  "Needs review": "warning",
  "AI investigated": "info",
  Resolved: "success",
};

export function RecentExceptions({ exceptions }) {
  return (
    <Card className="min-w-0">
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-4">
        <div className="space-y-1">
          <CardTitle>Recent exceptions</CardTitle>
          <CardDescription>Records that need a human decision</CardDescription>
        </div>
        <Button variant="ghost" size="sm" render={<Link href="/dashboard/exceptions" />}>
          View all
        </Button>
      </CardHeader>
      <CardContent className="px-0 pt-0">
        {exceptions.length === 0 ? (
          <div className="px-5">
            <EmptyState
              icon={TriangleAlert}
              title="No exceptions right now"
              description="When reconciliation finds records that don't match, they'll appear here for review."
            />
          </div>
        ) : (
          <ul role="list" className="divide-y divide-border">
            {exceptions.map((exception) => (
              <li key={exception.id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-5 py-3 transition-colors hover:bg-muted/40">
                <Badge variant={severityVariants[exception.severity] ?? "default"} className="uppercase tracking-wide text-[10px]">
                  {exception.severity}
                </Badge>
                <div className="min-w-0 flex-1 basis-48">
                  <p className="truncate text-sm font-medium text-foreground">
                    {exception.title} · {exception.amount}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">{exception.detail}</p>
                </div>
                <span className="text-xs tabular-nums text-muted-foreground">{exception.age}</span>
                <Badge variant={statusVariants[exception.status] ?? "outline"}>{exception.status}</Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
