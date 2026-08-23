import { Plug } from "lucide-react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/empty-state";
import { ActivityChart } from "@/components/dashboard/activity-chart";
import { AiSummary } from "@/components/dashboard/ai-summary";
import { RecentExceptions } from "@/components/dashboard/recent-exceptions";
import { StatsGrid } from "@/components/dashboard/stats-grid";
import { dashboardSummary } from "@/lib/demo-data";

function greetingFor(hour) {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export const metadata = { title: "Overview" };

/**
 * Day 1 dashboard: reads placeholder values from lib/demo-data.js.
 * When FastAPI exposes GET /api/dashboard/summary, only this page changes —
 * widgets already accept plain props.
 */
export default function DashboardPage() {
  const { totals, activity, recentExceptions, aiInvestigation } = dashboardSummary;
  const greeting = greetingFor(new Date().getHours());

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <header>
        <h1 className="text-[28px] font-semibold tracking-tight text-foreground sm:text-[32px]">
          {greeting}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground sm:text-[15px]">
          Here&rsquo;s what is happening with your financial data.
        </p>
      </header>

      <EmptyState
        icon={Plug}
        title="No financial activity yet"
        description="Connect your first financial source to begin reconciling your records automatically."
        action={
          <Button render={<a href="/dashboard/sources" />}>Connect a financial source</Button>
        }
      />

      <StatsGrid totals={totals} />

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <ActivityChart activity={activity} />
        <AiSummary investigation={aiInvestigation} />
      </div>

      <RecentExceptions exceptions={recentExceptions} />
    </div>
  );
}
