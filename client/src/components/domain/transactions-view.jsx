"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { DataTable } from "@/components/common/data-table";
import { CursorPagination } from "@/components/common/pagination";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { TransactionDrawer } from "@/components/domain/transaction-drawer";
import { humanize } from "@/components/domain/status-badge";
import {
  listTransactions,
} from "@/lib/api/transactions";
import { listSources } from "@/lib/api/sources";
import { formatDate, formatMoney } from "@/lib/format";

/**
 * Transactions screen. All filtering/pagination is server-side via the
 * backend's cursor API; the browser holds at most one page of rows.
 */
export function TransactionsView() {
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");

  const [sources, setSources] = useState([]);
  const [page, setPage] = useState({ items: [], nextCursor: null });
  const [cursorStack, setCursorStack] = useState([]); // cursors for pages beyond the first
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedTransactionId, setSelectedTransactionId] = useState(null);
  const [sourceId, setSourceId] = useState(ALL);
  const [direction, setDirection] = useState(ALL);
  const [status, setStatus] = useState(ALL);

  // Debounce search so typing doesn't hammer the API.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => {
    let cancelled = false;
    listSources({ limit: 100 })
      .then((result) => {
        if (!cancelled) setSources(result.items);
      })
      .catch(() => {
        // The table already reports load failures; the filter just loses options.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const activeFilters = useMemo(
    () => ({
      search,
      // "ALL" is the UI sentinel for "no filter"; never sent to the API.
      sourceId: sourceId === ALL ? "" : sourceId,
      direction: direction === ALL ? "" : direction,
      status: status === ALL ? "" : status,
    }),
    [search, sourceId, direction, status]
  );

  // All state updates happen in promise callbacks — never synchronously
  // inside the effect that starts the fetch.
  const loadPage = useCallback(
    ({ signal, cursor }) => {
      return listTransactions({ ...activeFilters, limit: 25, cursor, signal })
        .then((result) => {
          console.log(result)
          if (signal?.aborted) return;
          setPage(result);
          setError(null);
        })
        .catch((err) => {
          if (err?.name === "AbortError" || signal?.aborted) return;
          setError(err?.message || null);
          setPage({ items: [], nextCursor: null });
        })
        .finally(() => {
          if (!signal?.aborted) setLoading(false);
        });
    },
    [activeFilters]
  );

  useEffect(() => {
    // Filter changes restart the fetch; the abort of the previous request
    // prevents out-of-order overwrites.
    const controller = new AbortController();
    loadPage({ signal: controller.signal, cursor: null });
    return () => controller.abort();
  }, [loadPage]);

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

  // Filter changes restart from page one; the cursor history is only valid
  // for the filter combination it was captured under.
  function selectSource(value) {
    setSourceId(value);
    setCursorStack([]);
  }

  function selectDirection(value) {
    setDirection(value);
    setCursorStack([]);
  }

  function selectStatus(value) {
    setStatus(value);
    setCursorStack([]);
  }

  const hasActiveFilters =
    Boolean(search) ||
    sourceId !== ALL ||
    direction !== ALL ||
    status !== ALL;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="relative w-full lg:max-w-xs">
          <SearchIcon />
          <Input
            type="search"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search reference, description, counterparty…"
            aria-label="Search transactions"
            className="pl-8"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={sourceId}
            onValueChange={selectSource}
            items={sourceItems(sources)}
            placeholder="All sources"
            triggerClassName="w-44"
          />

          <Select
            value={direction}
            onValueChange={selectDirection}
            items={DIRECTION_ITEMS}
            placeholder="Direction"
            triggerClassName="w-32"
          />

          <Select
            value={status}
            onValueChange={selectStatus}
            items={STATUS_ITEMS}
            placeholder="Record status"
            triggerClassName="w-36"
          />

          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSearchInput("");
                setSourceId(ALL);
                setDirection(ALL);
                setStatus(ALL);
                setCursorStack([]);
              }}
            >
              Clear filters
            </Button>
          )}
        </div>
      </div>

      <DataTable
        columns={TRANSACTION_COLUMNS}
        rows={page.items}
        rowKey={(row) => row.id}
        loading={loading && page.items.length === 0}
        error={
          error ? (
            <ErrorState
              className="border-0"
              title="Unable to load transactions"
              message={error}
              onRetry={() => loadPage({ cursor: cursorStack[cursorStack.length - 1] ?? null })}
            />
          ) : null
        }
        empty={
          hasActiveFilters ? (
            <EmptyState
              title="No matching transactions"
              description="No transactions match these filters. Try adjusting your search or clearing filters."
            />
          ) : (
            <EmptyState
              title="No transactions yet"
              description="Import financial data from a source and every normalized transaction will appear here."
            />
          )
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
      />
    </div>
  );
}

function SearchIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
    >
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}

function sourceItems(sources) {
  return [
    { value: ALL, label: "All sources" },
    ...sources.map((s) => ({ value: s.id, label: s.name })),
  ];
}

const ALL = "ALL";

const DIRECTION_ITEMS = [
  { value: ALL, label: "Any direction" },
  { value: "CREDIT", label: "Credit" },
  { value: "DEBIT", label: "Debit" },
];

const STATUS_ITEMS = [
  { value: ALL, label: "Any record status" },
  { value: "SETTLED", label: "Settled" },
  { value: "PENDING", label: "Pending" },
  { value: "FAILED", label: "Failed" },
  { value: "CANCELLED", label: "Cancelled" },
];

const TRANSACTION_COLUMNS = [
  {
    key: "transactionDate",
    header: "Date",
    render: (row) => (
      <span className="whitespace-nowrap text-muted-foreground">{formatDate(row.transactionDate)}</span>
    ),
  },
  {
    key: "counterparty",
    header: "Description",
    render: (row) => (
      <div className="min-w-0 max-w-72">
        <p className="truncate font-medium text-foreground">{row.counterparty || row.description || "—"}</p>
        {row.description && row.counterparty && (
          <p className="truncate text-xs text-muted-foreground">{row.description}</p>
        )}
      </div>
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
    key: "currency",
    header: "Currency",
    render: (row) => <span className="text-muted-foreground">{row.currency}</span>,
  },
  {
    key: "direction",
    header: "Direction",
    render: (row) => (
      <span className="text-muted-foreground">
        {row.direction === "CREDIT" ? "Credit" : row.direction === "DEBIT" ? "Debit" : "—"}
      </span>
    ),
  },
  {
    key: "status",
    header: "Status",
    render: (row) => (
      <span className="text-muted-foreground">{humanize(row.status)}</span>
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
