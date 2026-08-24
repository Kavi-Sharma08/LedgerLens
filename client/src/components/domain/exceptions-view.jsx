"use client";

import { useCallback, useEffect, useState } from "react";
import { ShieldAlert } from "lucide-react";

import { Select } from "@/components/ui/select";
import { DataTable } from "@/components/common/data-table";
import { CursorPagination } from "@/components/common/pagination";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { Drawer, DetailField, DrawerSection } from "@/components/common/drawer";
import { StatusBadge, exceptionReasonLabel, humanize } from "@/components/domain/status-badge";
import { listExceptions } from "@/lib/api/exceptions";
import { formatDateTime } from "@/lib/format";

const ALL = "ALL";

const STATUS_FILTER_ITEMS = [
  { value: ALL, label: "All states" },
  { value: "OPEN", label: "Open" },
  { value: "RESOLVED", label: "Resolved" },
  { value: "DISMISSED", label: "Dismissed" },
];

/**
 * Workspace-wide exceptions feed across all runs. Filtering happens
 * server-side; the client only tracks the active filter and cursor.
 */
export function ExceptionsView() {
  const [statusFilter, setStatusFilter] = useState(ALL);
  const [page, setPage] = useState({ items: [], nextCursor: null });
  const [cursorStack, setCursorStack] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [detail, setDetail] = useState(null);

  const loadPage = useCallback(
    ({ signal, cursor }) => {
      // State updates stay inside promise callbacks — never synchronous in
      // the effect body that starts the fetch.
      return listExceptions({
        status: statusFilter === ALL ? "" : statusFilter,
        limit: 20,
        cursor,
        signal,
      })
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
    [statusFilter]
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
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Data-quality issues the engine flagged while reconciling your records.
        </p>
        <div className="w-40 shrink-0">
          <Select
            value={statusFilter}
            onValueChange={(value) => {
              // Filter changes restart from page one; cursor history is only
              // valid for the filter it was captured under.
              setStatusFilter(value);
              setCursorStack([]);
            }}
            items={STATUS_FILTER_ITEMS}
            placeholder="All states"
            triggerClassName="w-full"
          />
        </div>
      </div>

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
          statusFilter !== ALL ? (
            <EmptyState
              icon={ShieldAlert}
              title={`No ${humanize(statusFilter).toLowerCase()} exceptions`}
              description="Nothing matches this filter right now."
            />
          ) : (
            <EmptyState
              icon={ShieldAlert}
              title="No exceptions"
              description="When the reconciliation engine flags a data-quality issue — a currency mismatch, a possible fee, a failed record — it will appear here."
            />
          )
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

      <Drawer open={Boolean(detail)} onClose={() => setDetail(null)} label="Exception detail">
        {detail && (
          <div className="divide-y divide-border">
            <DrawerSection>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
                <div className="col-span-2 flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-foreground">
                    {exceptionReasonLabel(detail.reasonCode)}
                  </span>
                  <StatusBadge kind="exception" value={detail.status} />
                </div>
                <div className="col-span-2">
                  <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Engine detail</dt>
                  <dd className="mt-0.5 text-sm leading-relaxed text-muted-foreground">{detail.detail || "—"}</dd>
                </div>
                <DetailField label="Detected">{formatDateTime(detail.createdAt)}</DetailField>
              </dl>
            </DrawerSection>
            {detail.transactionIds?.length > 0 && (
              <DrawerSection title="Linked records">
                <ul role="list" className="space-y-2">
                  {detail.transactionIds.map((id) => (
                    <li key={id}>
                      <code className="block truncate rounded-md bg-muted px-2 py-1.5 font-mono text-xs text-foreground">
                        {id}
                      </code>
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-muted-foreground">
                  Open these records from the Transactions screen to inspect their details.
                </p>
              </DrawerSection>
            )}
          </div>
        )}
      </Drawer>
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
      <span className="block max-w-md truncate text-muted-foreground">{row.detail || "—"}</span>
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
