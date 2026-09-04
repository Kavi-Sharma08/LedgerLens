"use client";

import { useCallback, useEffect, useState } from "react";
import { History } from "lucide-react";

import { Select } from "@/components/ui/select";
import { DataTable } from "@/components/common/data-table";
import { CursorPagination } from "@/components/common/pagination";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { listAuditLogs } from "@/lib/api/audit";
import { formatDateTime } from "@/lib/format";
import { humanize } from "@/components/domain/status-badge";

const ALL = "ALL";

const ACTION_FILTER_ITEMS = [
  { value: ALL, label: "All actions" },
  { value: "workspace_created", label: "Workspace created" },
  { value: "role_changed", label: "Role changed" },
  { value: "member_removed", label: "Member removed" },
  { value: "source_created", label: "Source created" },
  { value: "file_uploaded", label: "File uploaded" },
  { value: "reconciliation_started", label: "Reconciliation started" },
  { value: "reconciliation_completed", label: "Reconciliation completed" },
  { value: "match_approved", label: "Match approved" },
  { value: "match_rejected", label: "Match rejected" },
  { value: "exception_assigned", label: "Exception assigned" },
  { value: "exception_status_changed", label: "Exception status changed" },
  { value: "exception_note_added", label: "Exception note added" },
];

const ACTION_LABELS = {
  workspace_created: "Workspace created",
  member_invited: "Member invited",
  member_accepted: "Member accepted",
  role_changed: "Role changed",
  member_removed: "Member removed",
  source_created: "Source created",
  file_uploaded: "File uploaded",
  reconciliation_started: "Reconciliation started",
  reconciliation_completed: "Reconciliation completed",
  match_approved: "Match approved",
  match_rejected: "Match rejected",
  exception_assigned: "Exception assigned",
  exception_status_changed: "Exception status changed",
  exception_note_added: "Exception note added",
  password_set: "Password set",
};

function formatAction(action) {
  return ACTION_LABELS[action] || action.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatEntity(entityType, entityId, details) {
  if (!entityType) return "—";
  if (entityType === "match" && details?.action) {
    return formatAction(details.action);
  }
  if (entityType === "exception" && details?.newStatus) {
    return `Exception → ${details.newStatus}`;
  }
  return humanize(entityType);
}

export function AuditView() {
  const [actionFilter, setActionFilter] = useState(ALL);
  const [page, setPage] = useState({ items: [], nextCursor: null });
  const [cursorStack, setCursorStack] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadPage = useCallback(
    ({ signal, cursor }) => {
      return listAuditLogs({
        action: actionFilter === ALL ? "" : actionFilter,
        limit: 25,
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
    [actionFilter]
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
          Immutable record of important actions in this workspace.
        </p>
        <div className="w-48 shrink-0">
          <Select
            value={actionFilter}
            onValueChange={(value) => {
              setActionFilter(value);
              setCursorStack([]);
            }}
            items={ACTION_FILTER_ITEMS}
            placeholder="All actions"
            triggerClassName="w-full"
          />
        </div>
      </div>

      <DataTable
        columns={AUDIT_COLUMNS}
        rows={page.items}
        rowKey={(row) => row.id}
        loading={loading && page.items.length === 0}
        error={
          error ? (
            <ErrorState
              className="border-0"
              title="Unable to load audit log"
              message={error}
              onRetry={() => loadPage({ cursor: cursorStack[cursorStack.length - 1] ?? null })}
            />
          ) : null
        }
        empty={
          actionFilter !== ALL ? (
            <EmptyState
              icon={History}
              title="No matching entries"
              description="No audit records match this filter."
            />
          ) : (
            <EmptyState
              icon={History}
              title="No audit records yet"
              description="Actions like source creation, reconciliation runs, and match decisions will appear here."
            />
          )
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

const AUDIT_COLUMNS = [
  {
    key: "createdAt",
    header: "Time",
    render: (row) => (
      <span className="whitespace-nowrap text-muted-foreground">{formatDateTime(row.createdAt)}</span>
    ),
  },
  {
    key: "action",
    header: "Action",
    render: (row) => (
      <span className="font-medium text-foreground">{formatAction(row.action)}</span>
    ),
  },
  {
    key: "entity",
    header: "Entity",
    render: (row) => (
      <span className="text-muted-foreground">{formatEntity(row.entityType, row.entityId, row.details)}</span>
    ),
  },
  {
    key: "userId",
    header: "User",
    render: (row) => (
      <span className="text-xs text-muted-foreground">
        {row.userId ? "Team member" : "—"}
      </span>
    ),
  },
];
