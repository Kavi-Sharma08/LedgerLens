"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeftRight, CircleCheck, ShieldAlert, TriangleAlert } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { AccessRestricted } from "@/components/common/access-restricted";
import { useDashboard } from "@/components/common/dashboard-context";
import { StatusBadge, exceptionReasonLabel } from "@/components/domain/status-badge";
import { getOverview } from "@/lib/api/overview";
import { listRuns } from "@/lib/api/reconciliations";
import { listExceptions } from "@/lib/api/exceptions";
import { formatCount, formatDateTime, formatRelativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Workspace overview. Every number comes from the backend's overview summary
 * and the latest run/exception feeds — nothing here is computed in the UI.
 */
export function OverviewView({ greeting }) {
  const { can } = useDashboard();
  const canViewData = Boolean(can.viewData);
  const [summary, setSummary] = useState(null);
  const [runs, setRuns] = useState([]);
  const [exceptions, setExceptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!canViewData) return;
    let cancelled = false;
    const controller = new AbortController();

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [overviewResult, runsResult, exceptionsResult] = await Promise.all([
          getOverview({ signal: controller.signal }),
          listRuns({ limit: 5, signal: controller.signal }),
          listExceptions({ limit: 5, signal: controller.signal }),
        ]);
        if (cancelled) return;
        setSummary(overviewResult);
        setRuns(runsResult.items);
        setExceptions(exceptionsResult.items);
      } catch (err) {
        if (cancelled || err?.name === "AbortError") return;
        setError(err?.message || null);
      } finally {
        if (!cancelled && !controller.signal.aborted) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [canViewData]);

  if (!canViewData) {
    return (
      <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        <header>
          <h1 className="text-[28px] font-semibold tracking-tight text-foreground sm:text-[32px]">
            {greeting}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground sm:text-[15px]">
            Welcome to your workspace.
          </p>
        </header>
        <AccessRestricted />
      </div>
    );
  }

  if (loading) return <OverviewSkeleton greeting={greeting} />;

  if (error) {
    return (
      <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        <header>
          <h1 className="text-[28px] font-semibold tracking-tight text-foreground sm:text-[32px]">
            {greeting}
          </h1>
        </header>
        <ErrorState
          title="Unable to load overview"
          message={error}
        />
      </div>
    );
  }

  const hasData = (summary?.totalTransactions ?? 0) > 0 || (summary?.sourcesCount ?? 0) > 0;
  const latestRun = summary?.latestRun ?? null;

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[28px] font-semibold tracking-tight text-foreground sm:text-[32px]">
            {greeting}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground sm:text-[15px]">
            Here&rsquo;s what is happening with your financial data.
          </p>
        </div>
        {latestRun && (
          <Button variant="outline" size="sm" render={<Link href={`/dashboard/reconciliations/${latestRun.id}`} />}>
            View latest reconciliation
          </Button>
        )}
      </header>

      {!hasData ? (
        <EmptyState
          icon={ArrowLeftRight}
          title="Welcome to LedgerLens"
          description="Add your first financial source to start reconciling transactions automatically."
          action={
            <Button render={<Link href="/dashboard/sources" />}>Add a source</Button>
          }
        />
      ) : (
        <>
          <section aria-label="Workspace summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <KpiCard
              label="Transactions"
              value={formatCount(summary.totalTransactions)}
              icon={ArrowLeftRight}
              iconClass="bg-primary/10 text-primary"
              hint="Normalized across all sources"
            />
            <KpiCard
              label="Connected sources"
              value={formatCount(summary.sourcesCount)}
              icon={CircleCheck}
              iconClass="bg-success/10 text-success"
              action={<Link className="text-xs font-medium text-primary hover:underline" href="/dashboard/sources">Manage</Link>}
            />
            <KpiCard
              label="Open exceptions"
              value={formatCount(summary.openExceptions)}
              icon={ShieldAlert}
              iconClass={
                (summary.openExceptions ?? 0) > 0
                  ? "bg-destructive/10 text-destructive"
                  : "bg-success/10 text-success"
              }
              action={<Link className="text-xs font-medium text-primary hover:underline" href="/dashboard/exceptions">Review</Link>}
            />
          </section>

          <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
            <Card className="min-w-0">
              <CardHeader className="flex-row items-center justify-between space-y-0 pb-4">
                <div className="space-y-1">
                  <CardTitle>Recent reconciliations</CardTitle>
                  <CardDescription>Your latest comparison runs</CardDescription>
                </div>
                <Button variant="ghost" size="sm" render={<Link href="/dashboard/reconciliations" />}>
                  View all
                </Button>
              </CardHeader>
              <CardContent className="px-0 pt-0">
                {runs.length === 0 ? (
                  <div className="px-5">
                    <EmptyState
                      icon={TriangleAlert}
                      title="No reconciliation runs yet"
                      description="Start one from the Reconciliations screen once you have at least two sources."
                    />
                  </div>
                ) : (
                  <ul role="list" className="divide-y divide-border">
                    {runs.map((run) => (
                      <li key={run.id}>
                        <Link
                          href={`/dashboard/reconciliations/${run.id}`}
                          className="flex items-center gap-3 px-5 py-3 outline-none transition-colors hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/50"
                        >
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium text-foreground">
                              Run · {run.sourceIds.length} sources
                            </span>
                            <span className="block text-xs text-muted-foreground">
                              {formatDateTime(run.startedAt)}
                            </span>
                          </span>
                          <span className="hidden items-center gap-3 text-xs tabular-nums sm:flex">
                            <span className="text-success">{formatCount(run.matchedCount)} matched</span>
                            {(run.exceptionCount > 0 || run.unmatchedCount > 0) && (
                              <span className="text-muted-foreground">
                                {formatCount(run.unmatchedCount)} unmatched
                                {run.exceptionCount > 0 &&
                                  ` · ${formatCount(run.exceptionCount)} exceptions`}
                              </span>
                            )}
                          </span>
                          <StatusBadge kind="run" value={run.status} />
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

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
                      description="When reconciliation flags a data-quality issue it will appear here."
                    />
                  </div>
                ) : (
                  <ul role="list" className="divide-y divide-border">
                    {exceptions.map((exception) => (
                      <li key={exception.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-5 py-3 transition-colors hover:bg-muted/40">
                        <div className="min-w-0 flex-1 basis-48">
                          <p className="truncate text-sm font-medium text-foreground">
                            {exceptionReasonLabel(exception.reasonCode)}
                          </p>
                          <p className="truncate text-xs text-muted-foreground">
                            {exception.detail}
                          </p>
                        </div>
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {formatRelativeTime(exception.createdAt)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </>
  );
}

function KpiCard({ label, value, icon: Icon, iconClass, hint, action }) {
  return (
    <Card className="gap-0 p-5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-[13px] text-muted-foreground">{label}</p>
          <p className="mt-2 text-2xl font-semibold tracking-tight tabular-nums text-foreground">
            {value}
          </p>
        </div>
        <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-lg", iconClass)}>
          <Icon className="size-4.5" aria-hidden="true" />
        </span>
      </div>
      <p className="mt-3 flex items-center justify-between gap-2 text-xs text-muted-foreground">
        {hint}
        {action}
      </p>
    </Card>
  );
}

function OverviewSkeleton({ greeting }) {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading overview">
      <header>
        <h1 className="text-[28px] font-semibold tracking-tight text-foreground sm:text-[32px]">
          {greeting}
        </h1>
      </header>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {[0, 1, 2].map((index) => (
          <Skeleton key={index} className="h-32 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Skeleton className="h-72 rounded-xl" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
    </div>
  );
}
