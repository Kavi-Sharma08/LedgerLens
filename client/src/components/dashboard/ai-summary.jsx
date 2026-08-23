"use client";

import { Sparkles } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function AiSummary({ investigation }) {
  return (
    <Card className="border-primary/20 bg-gradient-to-br from-accent/60 to-card">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Sparkles className="size-4 text-primary" aria-hidden="true" />
          <CardTitle>AI investigation</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm font-medium text-foreground">{investigation.headline}</p>
        <p className="text-sm leading-relaxed text-muted-foreground">{investigation.summary}</p>
        <ul className="space-y-2.5">
          {investigation.findings.map((finding) => (
            <li key={finding} className="flex gap-2.5 text-sm leading-relaxed text-muted-foreground">
              <span aria-hidden="true" className="mt-[7px] size-1.5 shrink-0 rounded-full bg-primary/60" />
              {finding}
            </li>
          ))}
        </ul>
        <p className="rounded-md border border-primary/15 bg-card px-3 py-2 text-xs leading-relaxed text-muted-foreground">
          AI prepares recommendations only — every resolution is confirmed by a human and recorded in
          the audit trail.
        </p>
      </CardContent>
    </Card>
  );
}
