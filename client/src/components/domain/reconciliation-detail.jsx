"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeftRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabPanel } from "@/components/ui/tabs";
import { DataTable } from "@/components/common/data-table";
import { CursorPagination } from "@/components/common/pagination";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { Drawer, DetailField, DrawerSection } from "@/components/common/drawer";
import { StatusBadge, exceptionReasonLabel, humanize } from "@/components/domain/status-badge";
import { ConfidenceIndicator } from "@/components/domain/confidence-indicator";
import { EvidenceList } from "@/components/domain/evidence-list";
import { MatchDrawer } from "@/components/domain/match-drawer";
import { ExceptionDetailDrawer } from "@/components/domain/exception-detail-drawer";
import { TransactionDrawer } from "@/components/domain/transaction-drawer";
import { AiAnalysis } from "@/components/domain/ai-analysis";
import { useDashboard } from "@/components/common/dashboard-context";
import { useAiContext } from "@/components/common/ai-context";
import { getRun, listRunMatches, listRunExceptions, listRunUnmatched, approveMatch, rejectMatch } from "@/lib/api/reconciliations";
import { analyzeReconciliation } from "@/lib/api/ai";
import { formatCount, formatDateTime, formatMoney } from "@/lib/format";
import { cn } from "@/lib/utils";

const TAB_VALUES = ["overview", "matched", "review", "unmatched", "exceptions"];

/**
 * Reconciliation run detail: summary plus tabbed result views.
 * Every number and row comes from the run's persisted results — the UI
 * never re-derives matching outcomes.
 */
export function ReconciliationDetail({ runId }) {
  const { setReconciliationContext } = useAiContext();
  const [loaded, setLoaded] = useState({ id: null, run: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("overview");

  useEffect(() => {
    const controller = new AbortController();
    getRun(runId, { signal: controller.signal })
      .then((run) => {
        if (controller.signal.aborted) return;
        setLoaded({ id: runId, run });
        setReconciliationContext(runId, run);
        setError(null);
      })
      .catch((err) => {
        if (err?.name === "AbortError" || controller.signal.aborted) return;
        setError(err?.message || null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [runId, setReconciliationContext]);


  if (error) {
    return (
      <ErrorState
        title="Unable to load this reconciliation"
        message={error}
        action={
          <Button variant="outline" size="sm" render={<Link href="/dashboard/reconciliations" />}>
            Back to reconciliations
          </Button>
        }
      />
    );
  }

  if (loading || loaded.id !== runId || !loaded.run) {
    return <DetailSkeleton />;
  }

  const run = loaded.run;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2.5 text-xl font-semibold tracking-tight text-foreground">
            Run <span className="font-mono text-lg">{shortId(run.id)}</span>
            <StatusBadge kind="run" value={run.status} />
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {formatDateTime(run.startedAt)}
            {run.completedAt ? ` — completed ${formatDateTime(run.completedAt)}` : ""}
            {" · "}
            {run.sourceIds.length} sources · engine v{run.algorithmVersion}
          </p>
        </div>
      </header>

      <nav aria-label="Breadcrumb" className="text-sm">
        <Link
          href="/dashboard/reconciliations"
          className="inline-flex items-center gap-1 text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/50 rounded-sm"
        >
          All reconciliations
        </Link>
      </nav>

      <Tabs
        ariaLabel="Reconciliation results"
        value={tab}
        onValueChange={setTab}
        items={[
          { value: "overview", label: "Overview" },
          { value: "matched", label: "Matched", count: run.matchedCount },
          { value: "review", label: "Needs review", count: run.likelyMatchCount + run.ambiguousCount },
          { value: "unmatched", label: "Unmatched", count: run.unmatchedCount },
          { value: "exceptions", label: "Exceptions", count: run.exceptionCount },
        ]}
      />

      <TabPanel value="overview" active={tab === "overview"}>
        <OverviewPanel run={run} onJump={setTab} />
      </TabPanel>
      <TabPanel value="matched" active={tab === "matched"}>
        <MatchesPanel runId={runId} statuses={["MATCHED"]} emptyTitle="No exact matches" emptyDescription="This run did not produce any confirmed matches." />
      </TabPanel>
      <TabPanel value="review" active={tab === "review"}>
        <MatchesPanel runId={runId} statuses={["LIKELY_MATCH", "AMBIGUOUS"]} emptyTitle="Nothing to review" emptyDescription="No records in this run need human review." />
      </TabPanel>
      <TabPanel value="unmatched" active={tab === "unmatched"}>
        <UnmatchedPanel runId={runId} />
      </TabPanel>
      <TabPanel value="exceptions" active={tab === "exceptions"}>
        <ExceptionsPanel runId={runId} />
      </TabPanel>
    </div>
  );
}

function OverviewPanel({ run, onJump }) {
  const reviewed = run.matchedCount;
  const total = Math.max(run.totalTransactions, 1);

  const kpis = [
    { label: "Transactions compared", value: run.totalTransactions, tone: "default", tab: null },
    { label: "Matched", value: run.matchedCount, tone: "success", tab: "matched" },
    { label: "Likely matches", value: run.likelyMatchCount, tone: "info", tab: "review" },
    { label: "Ambiguous", value: run.ambiguousCount, tone: "warning", tab: "review" },
    { label: "Unmatched", value: run.unmatchedCount, tone: "neutral", tab: "unmatched" },
    { label: "Exceptions", value: run.exceptionCount, tone: "destructive", tab: "exceptions" },
  ];

  return (
    <div className="space-y-5 pt-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {kpis.map((kpi) => {
          const content = (
            <>
              <span className="text-xs font-medium text-muted-foreground">{kpi.label}</span>
              <span className={cn(
                "mt-1 text-xl font-semibold tabular-nums",
                kpi.tone === "success" && "text-success",
                kpi.tone === "info" && "text-info",
                kpi.tone === "warning" && "text-warning",
                kpi.tone === "destructive" && "text-destructive",
                (kpi.tone === "default" || kpi.tone === "neutral") && "text-foreground"
              )}>
                {formatCount(kpi.value)}
              </span>
            </>
          );
          return kpi.tab ? (
            <button
              key={kpi.label}
              type="button"
              onClick={() => onJump(kpi.tab)}
              className="rounded-xl border border-border bg-card px-4 py-3 text-left transition-colors outline-none hover:bg-muted/40 focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              {content}
            </button>
          ) : (
            <div key={kpi.label} className="rounded-xl border border-border bg-card px-4 py-3">
              {content}
            </div>
          );
        })}
      </div>

      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium text-foreground">Reconciliation progress</span>
          <span className="text-muted-foreground">
            {formatCount(reviewed)} of {formatCount(run.totalTransactions)} records resolved
          </span>
        </div>
        <div
          role="meter"
          aria-valuenow={Math.round((reviewed / total) * 100)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Records resolved"
          className="mt-3 h-2 overflow-hidden rounded-full bg-muted"
        >
          <div
            className="h-full rounded-full bg-success transition-[width] duration-500"
            style={{ width: `${(reviewed / total) * 100}%` }}
          />
        </div>
        {run.error && (
          <p role="alert" className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {run.error}
          </p>
        )}
      </div>

      <dl className="grid gap-x-8 gap-y-3 rounded-xl border border-border bg-card p-4 sm:grid-cols-2">
        <DetailField label="Scope start">{run.dateFrom || "All time"}</DetailField>
        <DetailField label="Scope end">{run.dateTo || "All time"}</DetailField>
        <DetailField label="Engine version">{run.algorithmVersion || "—"}</DetailField>
        <DetailField label="Sources in scope">
          <span className="font-mono text-xs">{run.sourceIds.length} selected</span>
        </DetailField>
      </dl>

      <div className="rounded-xl border border-border bg-card p-4">
        <AiAnalysis
          label="Ask AI for a summary"
          analyze={({ signal }) => analyzeReconciliation(run.id, { signal })}
        />
      </div>
    </div>
  );
}

function MatchesPanel({ runId, statuses, emptyTitle, emptyDescription }) {
  const [page, setPage] = useState({ items: [], nextCursor: null });
  const [cursorStack, setCursorStack] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(null);
  const [selectedMatch, setSelectedMatch] = useState(null);
  const [acting, setActing] = useState(null);
  const { can } = useDashboard();

  const loadPage = useCallback(
    ({ signal, cursor }) => {
      // State updates stay inside promise callbacks (never synchronous in the
      // effect body that starts the fetch).
      return listRunMatches(runId, { statuses, limit: 20, cursor, signal })
        .then((result) => {
          if (!signal?.aborted) {
            setPage(result);
            setError(null);
          }
        })
        .catch((err) => {
          if (err?.name === "AbortError" || signal?.aborted) return;
          setError(err?.message || null);
        })
        .finally(() => {
          if (!signal?.aborted) setLoading(false);
        });
    },
    [runId, statuses]
  );

  useEffect(() => {
    const controller = new AbortController();
    loadPage({ signal: controller.signal, cursor: null });
    return () => controller.abort();
  }, [loadPage]);

  function goToNextPage() {
    if (!page.nextCursor) return;
    setCursorStack((stack) => [...stack, page.nextCursor]);
    loadPage({ cursor: page.nextCursor });
  }

  function goToPrevPage() {
    setCursorStack((stack) => {
      const next = stack.slice(0, -1);
      loadPage({ cursor: next[next.length - 1] ?? null });
      return next;
    });
  }

  async function handleApprove(row, event) {
    event.stopPropagation();
    setActing(row.id);
    try {
      await approveMatch(runId, row.id);
      loadPage({ cursor: cursorStack[cursorStack.length - 1] ?? null });
    } catch {
      // Error handled by keeping the button enabled
    } finally {
      setActing(null);
    }
  }

  async function handleReject(row, event) {
    event.stopPropagation();
    setActing(row.id);
    try {
      await rejectMatch(runId, row.id);
      loadPage({ cursor: cursorStack[cursorStack.length - 1] ?? null });
    } catch {
      // Error handled by keeping the button enabled
    } finally {
      setActing(null);
    }
  }

  const canReview = (row) => {
    return (statuses.includes("LIKELY_MATCH") || statuses.includes("AMBIGUOUS")) && !row.humanDecision;
  };

  async function openEvidence(row, event) {
    event.stopPropagation();
    setExpanded((current) => (current === row.id ? null : row.id));
  }

  return (
    <div className="space-y-3 pt-4">
      <DataTable
        columns={[
          ...MATCH_COLUMNS,
          {
            key: "actions",
            header: "",
            align: "right",
            render: (row) => (
              <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                {canReview(row) && acting !== row.id && can.approveMatches && (
                  <>
                    <Button
                      variant="ghost"
                      size="xs"
                      className="text-success hover:text-success"
                      onClick={(e) => handleApprove(row, e)}
                    >
                      Approve
                    </Button>
                    <Button
                      variant="ghost"
                      size="xs"
                      className="text-destructive hover:text-destructive"
                      onClick={(e) => handleReject(row, e)}
                    >
                      Reject
                    </Button>
                  </>
                )}
                {acting === row.id && (
                  <span className="text-xs text-muted-foreground">Saving...</span>
                )}
                {row.humanDecision && (
                  <Badge variant={row.humanDecision.action === "APPROVED" ? "success" : "destructive"} className="text-xs">
                    {row.humanDecision.action === "APPROVED" ? "Approved" : "Rejected"}
                  </Badge>
                )}
                <Button
                  variant="ghost"
                  size="xs"
                  onClick={(event) => openEvidence(row, event)}
                  aria-expanded={expanded === row.id}
                >
                  {expanded === row.id ? "Hide evidence" : "Evidence"}
                </Button>
              </div>
            ),
          },
        ]}
        rows={page.items}
        rowKey={(row) => row.id}
        loading={loading && page.items.length === 0}
        error={
          error ? (
            <ErrorState
              className="border-0"
              title="Unable to load matches"
              message={error}
              onRetry={() => loadPage({ cursor: cursorStack[cursorStack.length - 1] ?? null })}
            />
          ) : null
        }
        empty={
          <EmptyState icon={ArrowLeftRight} title={emptyTitle} description={emptyDescription} />
        }
        onRowClick={(row) => setSelectedMatch(row)}
      />

      {page.items.map(
        (row) =>
          expanded === row.id && (
            <div key={`evidence-${row.id}`} className="rounded-xl border border-border bg-card p-4">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <Badge variant="primary">{humanize(row.matchType)}</Badge>
                <StatusBadge kind="reconciliation" value={row.status} />
                {row.mismatchedFields?.length > 0 && (
                  <span className="text-xs text-muted-foreground">
                    Differing fields: {row.mismatchedFields.map(humanize).join(", ")}
                  </span>
                )}
              </div>
              <EvidenceList scoreBreakdown={row.scoreBreakdown} reasons={row.reasons} />
            </div>
          )
      )}

      {(page.nextCursor || cursorStack.length > 0) && !error && (
        <CursorPagination
          hasPrev={cursorStack.length > 0}
          hasNext={Boolean(page.nextCursor)}
          onPrev={goToPrevPage}
          onNext={goToNextPage}
        />
      )}

      <MatchDrawer
        match={selectedMatch}
        runId={runId}
        onClose={() => setSelectedMatch(null)}
        onDecision={() => loadPage({ cursor: cursorStack[cursorStack.length - 1] ?? null })}
      />
    </div>
  );
}

const MATCH_COLUMNS = [
  {
    key: "confidence",
    header: "Confidence",
    render: (row) => <ConfidenceIndicator confidence={row.confidence} />,
  },
  {
    key: "matchType",
    header: "Type",
    render: (row) => humanize(row.matchType),
  },
  {
    key: "status",
    header: "Status",
    render: (row) => <StatusBadge kind="reconciliation" value={row.status} />,
  },
  {
    key: "reasons",
    header: "Notes",
    render: (row) => (
      <span className="line-clamp-1 max-w-64 text-muted-foreground">
        {row.reasons?.length ? row.reasons.map(humanize).join("; ") : "—"}
      </span>
    ),
  },
];

function UnmatchedPanel({ runId }) {
  const [page, setPage] = useState({ items: [], nextCursor: null });
  const [cursorStack, setCursorStack] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedTransactionId, setSelectedTransactionId] = useState(null);

  const loadPage = useCallback(
    ({ signal, cursor }) => {
      return listRunUnmatched(runId, { limit: 20, cursor, signal })
        .then((result) => {
          if (!signal?.aborted) {
            setPage(result);
            setError(null);
          }
        })
        .catch((err) => {
          if (err?.name === "AbortError" || signal?.aborted) return;
          setError(err?.message || null);
        })
        .finally(() => {
          if (!signal?.aborted) setLoading(false);
        });
    },
    [runId]
  );

  useEffect(() => {
    const controller = new AbortController();
    loadPage({ signal: controller.signal, cursor: null });
    return () => controller.abort();
  }, [loadPage]);

  function goToNextPage() {
    if (!page.nextCursor) return;
    setCursorStack((stack) => [...stack, page.nextCursor]);
    loadPage({ cursor: page.nextCursor });
  }

  function goToPrevPage() {
    setCursorStack((stack) => {
      const next = stack.slice(0, -1);
      loadPage({ cursor: next[next.length - 1] ?? null });
      return next;
    });
  }

  return (
    <div className="space-y-3 pt-4">
      <p className="text-sm text-muted-foreground">
        Records with no counterpart in the other sources for this run.
      </p>
      <DataTable
        columns={UNMATCHED_COLUMNS}
        rows={page.items}
        rowKey={(row) => row.id}
        loading={loading && page.items.length === 0}
        error={
          error ? (
            <ErrorState
              className="border-0"
              title="Unable to load unmatched records"
              message={error}
              onRetry={() => loadPage({ cursor: cursorStack[cursorStack.length - 1] ?? null })}
            />
          ) : null
        }
        empty={
          <EmptyState
            icon={ArrowLeftRight}
            title="No unmatched records"
            description="Every record found a counterpart in this run."
          />
        }
        onRowClick={(row) => setSelectedTransactionId(row.id)}
      />

      {(page.nextCursor || cursorStack.length > 0) && !error && (
        <CursorPagination
          hasPrev={cursorStack.length > 0}
          hasNext={Boolean(page.nextCursor)}
          onPrev={goToPrevPage}
          onNext={goToNextPage}
        />
      )}

      <TransactionDrawer
        transactionId={selectedTransactionId}
        onClose={() => setSelectedTransactionId(null)}
        context={{ kind: "unmatched", runId }}
      />
    </div>
  );
}

const UNMATCHED_COLUMNS = [
  {
    key: "transactionDate",
    header: "Date",
    render: (row) => (
      <span className="whitespace-nowrap text-muted-foreground">{row.transactionDate}</span>
    ),
  },
  {
    key: "counterparty",
    header: "Counterparty",
    render: (row) => (
      <span className="block max-w-56 truncate font-medium text-foreground">
        {row.counterparty || "—"}
      </span>
    ),
  },
  {
    key: "description",
    header: "Description",
    render: (row) => (
      <span className="block max-w-72 truncate text-muted-foreground">
        {row.description || "—"}
      </span>
    ),
  },
  {
    key: "amount",
    header: "Amount",
    align: "right",
    render: (row) => (
      <span className="font-medium text-foreground">{formatMoney(row.amount, row.currency)}</span>
    ),
  },
  {
    key: "reference",
    header: "Reference",
    render: (row) => (
      <span className="font-mono text-xs text-muted-foreground">{row.reference || "—"}</span>
    ),
  },
];

function ExceptionsPanel({ runId }) {
  const [page, setPage] = useState({ items: [], nextCursor: null });
  const [cursorStack, setCursorStack] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [detail, setDetail] = useState(null);

  const loadPage = useCallback(
    ({ signal, cursor }) => {
      return listRunExceptions(runId, { limit: 20, cursor, signal })
        .then((result) => {
          if (!signal?.aborted) {
            setPage(result);
            setError(null);
          }
        })
        .catch((err) => {
          if (err?.name === "AbortError" || signal?.aborted) return;
          setError(err?.message || null);
        })
        .finally(() => {
          if (!signal?.aborted) setLoading(false);
        });
    },
    [runId]
  );

  useEffect(() => {
    const controller = new AbortController();
    loadPage({ signal: controller.signal, cursor: null });
    return () => controller.abort();
  }, [loadPage]);

  function goToNextPage() {
    if (!page.nextCursor) return;
    setCursorStack((stack) => [...stack, page.nextCursor]);
    loadPage({ cursor: page.nextCursor });
  }

  function goToPrevPage() {
    setCursorStack((stack) => {
      const next = stack.slice(0, -1);
      loadPage({ cursor: next[next.length - 1] ?? null });
      return next;
    });
  }

  return (
    <div className="space-y-3 pt-4">
      <DataTable
        columns={EXCEPTION_COLUMNS}
        rows={page.items}
        rowKey={(row) => row.id}
        loading={loading && page.items.length === 0}
        error={
          error ? (
            <ErrorState
              className="border-0"
              title="Unable to load exceptions"
              message={error}
              onRetry={() => loadPage({ cursor: cursorStack[cursorStack.length - 1] ?? null })}
            />
          ) : null
        }
        empty={
          <EmptyState
            title="No exceptions"
            description="The engine didn't flag any data-quality issues in this run."
          />
        }
        onRowClick={(row) => setDetail(row)}
      />

      {(page.nextCursor || cursorStack.length > 0) && !error && (
        <CursorPagination
          hasPrev={cursorStack.length > 0}
          hasNext={Boolean(page.nextCursor)}
          onPrev={goToPrevPage}
          onNext={goToNextPage}
        />
      )}

      <ExceptionDetailDrawer
        key={detail?.id ?? "none"}
        exception={detail}
        onClose={() => setDetail(null)}
        onStatusChange={(status) => {
          setDetail((d) => (d ? { ...d, status } : d));
          loadPage({ cursor: cursorStack[cursorStack.length - 1] ?? null });
        }}
        onNoteAdded={() =>
          loadPage({ cursor: cursorStack[cursorStack.length - 1] ?? null })
        }
      />
    </div>
  );
}

const EXCEPTION_COLUMNS = [
  {
    key: "reasonCode",
    header: "Issue",
    render: (row) => (
      <span className="font-medium text-foreground">{exceptionReasonLabel(row.reasonCode)}</span>
    ),
  },
  {
    key: "detail",
    header: "Detail",
    render: (row) => (
      <span className="block max-w-96 truncate text-muted-foreground">{row.detail || "—"}</span>
    ),
  },
  {
    key: "status",
    header: "State",
    render: (row) => <StatusBadge kind="exception" value={row.status} />,
  },
  {
    key: "createdAt",
    header: "Detected",
    render: (row) => (
      <span className="whitespace-nowrap text-muted-foreground">{formatDateTime(row.createdAt)}</span>
    ),
  },
];

function DetailSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading reconciliation">
      <Skeleton className="h-7 w-72" />
      <Skeleton className="h-4 w-96" />
      <Skeleton className="h-9 w-full max-w-md" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-20 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-80 w-full rounded-xl" />
    </div>
  );
}

function shortId(id) {
  return String(id).slice(-8).toUpperCase();
}
