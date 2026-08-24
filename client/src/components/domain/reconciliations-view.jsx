"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeftRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { DataTable } from "@/components/common/data-table";
import { CursorPagination } from "@/components/common/pagination";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { StatusBadge } from "@/components/domain/status-badge";
import { listRuns, startRun } from "@/lib/api/reconciliations";
import { listSources } from "@/lib/api/sources";
import { formatCount, formatDate } from "@/lib/format";

/**
 * Reconciliation runs screen: history of runs plus starting a new one.
 * Starting a run is a backend operation — the UI only selects sources and
 * reports the resulting run.
 */
export function ReconciliationsView() {
  const [page, setPage] = useState({ items: [], nextCursor: null });
  const [cursorStack, setCursorStack] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [runDialogOpen, setRunDialogOpen] = useState(false);

  const loadPage = useCallback(({ signal, cursor }) => {
    // State updates stay inside promise callbacks — the effect body that
    // triggers the initial load never mutates state synchronously.
    return listRuns({ limit: 20, cursor, signal })
      .then((result) => {
        if (signal?.aborted) return;
        setPage(result);
        setError(null);
      })
      .catch((err) => {
        if (err?.name === "AbortError" || signal?.aborted) return;
        setError(err?.message || null);
      })
      .finally(() => {
        if (!signal?.aborted) setLoading(false);
      });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    loadPage({ signal: controller.signal, cursor: null });
    return () => controller.abort();
  }, [loadPage]);

  function refresh() {
    setCursorStack([]);
    loadPage({ cursor: null });
  }

  function goToNextPage() {
    if (!page.nextCursor) return;
    const nextCursor = page.nextCursor;
    setCursorStack((stack) => [...stack, nextCursor]);
    loadPage({ cursor: nextCursor });
  }

  function goToPrevPage() {
    setCursorStack((stack) => {
      const next = stack.slice(0, -1);
      loadPage({ cursor: next[next.length - 1] ?? null });
      return next;
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Compare records across two or more sources to find matches and issues.
        </p>
        <StartReconciliationDialog
          open={runDialogOpen}
          onOpenChange={setRunDialogOpen}
          onStarted={refresh}
        />
      </div>

      <DataTable
        columns={RUN_COLUMNS}
        rows={page.items}
        rowKey={(row) => row.id}
        loading={loading && page.items.length === 0}
        error={
          error ? (
            <ErrorState
              className="border-0"
              title="Unable to load reconciliations"
              message={error}
              onRetry={() => loadPage({ cursor: cursorStack[cursorStack.length - 1] ?? null })}
            />
          ) : null
        }
        empty={
          <EmptyState
            icon={ArrowLeftRight}
            title="No reconciliation runs yet"
            description="Once you have data from at least two sources, start your first reconciliation to match records automatically."
          />
        }
      />

      {(page.nextCursor || cursorStack.length > 0) && !error && (
        <CursorPagination
          hasPrev={cursorStack.length > 0}
          hasNext={Boolean(page.nextCursor)}
          onPrev={goToPrevPage}
          onNext={goToNextPage}
        />
      )}
    </div>
  );
}

const RUN_COLUMNS = [
  {
    key: "id",
    header: "Run",
    render: (row) => (
      <Link
        href={`/dashboard/reconciliations/${row.id}`}
        className="font-mono text-xs font-medium text-primary underline-offset-4 hover:underline focus-visible:ring-2 focus-visible:ring-ring/50 outline-none rounded-sm"
      >
        {shortRunId(row.id)}
      </Link>
    ),
  },
  {
    key: "sourceIds",
    header: "Sources",
    render: (row) => (
      <span className="flex items-center gap-1 text-muted-foreground" aria-label={`${row.sourceIds.length} sources`}>
        <span className="tabular-nums">{row.sourceIds.length}</span>
        <span>sources compared</span>
      </span>
    ),
  },
  {
    key: "totalTransactions",
    header: "Transactions",
    align: "right",
    render: (row) => <span className="text-foreground">{formatCount(row.totalTransactions)}</span>,
  },
  {
    key: "matchedCount",
    header: "Matched",
    align: "right",
    render: (row) => <span className="text-success">{formatCount(row.matchedCount)}</span>,
  },
  {
    key: "needsReview",
    header: "Review",
    align: "right",
    render: (row) => (
      <span className="text-warning">
        {formatCount(row.likelyMatchCount + row.ambiguousCount)}
      </span>
    ),
  },
  {
    key: "exceptionCount",
    header: "Exceptions",
    align: "right",
    render: (row) => <span className="text-destructive">{formatCount(row.exceptionCount)}</span>,
  },
  {
    key: "status",
    header: "Status",
    render: (row) => <StatusBadge kind="run" value={row.status} />,
  },
  {
    key: "startedAt",
    header: "Started",
    render: (row) => (
      <span className="whitespace-nowrap text-muted-foreground">{formatDate(row.startedAt)}</span>
    ),
  },
];

function shortRunId(id) {
  return `R-${String(id).slice(-6).toUpperCase()}`;
}

function StartReconciliationDialog({ open, onOpenChange, onStarted }) {
  const [sources, setSources] = useState([]);
  const [selected, setSelected] = useState([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    listSources({ limit: 100 })
      .then((result) => {
        if (!cancelled) setSources(result.items);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [open]);

  async function handleStart(event) {
    event.preventDefault();
    setStarting(true);
    setError(null);
    try {
      await startRun({ sourceIds: selected });
      setSelected([]);
      onOpenChange(false);
      onStarted();
    } catch (err) {
      setError(err?.message || "The reconciliation couldn't be started.");
    } finally {
      setStarting(false);
    }
  }

  function toggle(sourceId) {
    setSelected((current) =>
      current.includes(sourceId)
        ? current.filter((id) => id !== sourceId)
        : [...current, sourceId]
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger render={<Button size="sm">Start reconciliation</Button>} />
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleStart}>
          <DialogHeader>
            <DialogTitle>Start reconciliation</DialogTitle>
            <DialogDescription>
              Select two or more sources. LedgerLens compares every record between
              them using its matching engine — this may take a moment for large imports.
            </DialogDescription>
          </DialogHeader>

          {sources.length < 2 ? (
            <div className="my-5 rounded-lg border border-dashed border-border bg-muted/30 px-4 py-6 text-center">
              <p className="text-sm font-medium text-foreground">
                You need at least two sources.
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Connect another financial source before running a reconciliation.
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-4"
                render={<Link href="/dashboard/sources" />}
              >
                View sources
              </Button>
            </div>
          ) : (
            <fieldset className="my-4">
              <legend className="sr-only">Sources to reconcile</legend>
              <ul role="list" className="max-h-64 space-y-1.5 overflow-y-auto pr-1">
                {sources.map((source) => {
                  const checked = selected.includes(source.id);
                  return (
                    <li key={source.id}>
                      <label className={cnCheckbox(checked)} aria-checked={checked}>
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggle(source.id)}
                          className="accent-primary"
                        />
                        <span className="min-w-0 flex-1 truncate text-sm text-foreground">
                          {source.name}
                        </span>
                        <span className="shrink-0 text-xs uppercase tracking-wide text-muted-foreground">
                          {source.type.replace("_", " ")}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            </fieldset>
          )}

          {error && (
            <p role="alert" className="mb-3 text-sm text-destructive">
              {error}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={selected.length < 2 || starting}>
              {starting ? "Reconciling…" : "Start reconciliation"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function cnCheckbox(checked) {
  return [
    "flex w-full cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-2 transition-colors outline-none",
    checked ? "border-primary/40 bg-accent" : "border-border hover:bg-muted/60",
    "focus-visible:ring-2 focus-visible:ring-ring/50",
  ].join(" ");
}
