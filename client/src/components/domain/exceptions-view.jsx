"use client";

import { useCallback, useEffect, useState } from "react";
import { ShieldAlert } from "lucide-react";

import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "@/components/common/data-table";
import { CursorPagination } from "@/components/common/pagination";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { Drawer, DetailField, DrawerSection } from "@/components/common/drawer";
import { StatusBadge, exceptionReasonLabel, humanize } from "@/components/domain/status-badge";
import {
  listExceptions,
  updateExceptionStatus,
  addExceptionNote,
} from "@/lib/api/exceptions";
import { formatDateTime } from "@/lib/format";

const ALL = "ALL";

const STATUS_FILTER_ITEMS = [
  { value: ALL, label: "All states" },
  { value: "OPEN", label: "Open" },
  { value: "INVESTIGATING", label: "Investigating" },
  { value: "RESOLVED", label: "Resolved" },
  { value: "DISMISSED", label: "Dismissed" },
];

const STATUS_ACTIONS = [
  { value: "INVESTIGATING", label: "Start investigating" },
  { value: "RESOLVED", label: "Mark resolved" },
  { value: "DISMISSED", label: "Dismiss" },
  { value: "OPEN", label: "Reopen" },
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
  const [noteText, setNoteText] = useState("");
  const [acting, setActing] = useState(false);

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

  async function handleStatusChange(exceptionId, newStatus) {
    setActing(true);
    try {
      await updateExceptionStatus(exceptionId, newStatus);
      // Refresh the detail and the list
      const updated = page.items.find((item) => item.id === exceptionId);
      if (updated) {
        setDetail({ ...updated, status: newStatus });
      }
      loadPage({ cursor: cursorStack[cursorStack.length - 1] ?? null });
    } catch {
      // Error silently handled
    } finally {
      setActing(false);
    }
  }

  async function handleAddNote(exceptionId) {
    if (!noteText.trim()) return;
    setActing(true);
    try {
      await addExceptionNote(exceptionId, noteText.trim());
      setNoteText("");
      // Refresh the list to get updated data
      loadPage({ cursor: cursorStack[cursorStack.length - 1] ?? null });
    } catch {
      // Error silently handled
    } finally {
      setActing(false);
    }
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
        onRowClick={(row) => {
          setDetail(row);
          setNoteText("");
        }}
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
                {detail.assignedTo && (
                  <DetailField label="Assigned to">
                    <span className="font-mono text-xs">{detail.assignedTo}</span>
                  </DetailField>
                )}
                <DetailField label="Detected">{formatDateTime(detail.createdAt)}</DetailField>
              </dl>
            </DrawerSection>

            {/* Status actions */}
            <DrawerSection title="Actions">
              <div className="flex flex-wrap gap-2">
                {STATUS_ACTIONS.filter((a) => a.value !== detail.status).map((action) => (
                  <Button
                    key={action.value}
                    variant="outline"
                    size="sm"
                    disabled={acting}
                    onClick={() => handleStatusChange(detail.id, action.value)}
                  >
                    {action.label}
                  </Button>
                ))}
              </div>
            </DrawerSection>

            {/* Notes */}
            <DrawerSection title="Investigation notes">
              {detail.notes && detail.notes.length > 0 && (
                <ul role="list" className="mb-4 space-y-3">
                  {detail.notes.map((note, idx) => (
                    <li key={idx} className="rounded-lg bg-muted/50 px-3 py-2">
                      <p className="text-sm leading-relaxed text-foreground">{note.text}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {note.userId && <span className="font-mono">{note.userId.slice(-6)}</span>}
                        {note.createdAt && <> · {formatDateTime(note.createdAt)}</>}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="Add a note..."
                  className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring/50"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleAddNote(detail.id);
                    }
                  }}
                />
                <Button
                  size="sm"
                  variant="outline"
                  disabled={acting || !noteText.trim()}
                  onClick={() => handleAddNote(detail.id)}
                >
                  Add
                </Button>
              </div>
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
    key: "assignedTo",
    header: "Assigned",
    render: (row) => (
      <span className="font-mono text-xs text-muted-foreground">
        {row.assignedTo ? row.assignedTo.slice(-6) : "—"}
      </span>
    ),
  },
  {
    key: "createdAt",
    header: "Detected",
    render: (row) => (
      <span className="whitespace-nowrap text-muted-foreground">{formatDateTime(row.createdAt)}</span>
    ),
  },
];
