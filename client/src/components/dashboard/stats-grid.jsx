"use client";

import {
  ArrowDownRight,
  ArrowLeftRight,
  ArrowUpRight,
  CircleCheck,
  CircleDashed,
  TriangleAlert,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const CARDS = [
  {
    key: "transactions",
    label: "Total transactions",
    icon: ArrowLeftRight,
    iconClass: "bg-primary/10 text-primary",
    valueIsPositive: true,
  },
  {
    key: "matched",
    label: "Matched",
    icon: CircleCheck,
    iconClass: "bg-success/10 text-success",
    valueIsPositive: true,
  },
  {
    key: "needsReview",
    label: "Needs review",
    icon: TriangleAlert,
    iconClass: "bg-warning/15 text-warning",
    valueIsPositive: false,
  },
  {
    key: "unresolved",
    label: "Unresolved",
    icon: CircleDashed,
    iconClass: "bg-destructive/10 text-destructive",
    valueIsPositive: false,
  },
];

export function StatsGrid({ totals }) {
  return (
    <section aria-label="Reconciliation summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {CARDS.map((card) => (
        <Card key={card.key} className="gap-0 p-5">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[13px] text-muted-foreground">{card.label}</p>
              <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums text-foreground">
                {totals[card.key].value.toLocaleString()}
              </p>
            </div>
            <span className={cn("flex size-9 items-center justify-center rounded-lg", card.iconClass)}>
              <card.icon className="size-4.5" aria-hidden="true" />
            </span>
          </div>
          <p className="mt-3 flex items-center gap-1 text-xs text-muted-foreground">
            <DeltaIcon direction={totals[card.key].direction} positive={card.valueIsPositive} />
            {totals[card.key].delta}
          </p>
        </Card>
      ))}
    </section>
  );
}

function DeltaIcon({ direction, positive }) {
  if (!direction) return null;
  const Icon = direction === "up" ? ArrowUpRight : ArrowDownRight;
  // For "good when down" metrics, an up arrow is still colored by whether the
  // movement is favorable — color communicates favorability, not raw direction.
  return (
    <Icon
      className={cn("size-3", positive ? "text-success" : "text-muted-foreground")}
      aria-hidden="true"
    />
  );
}
