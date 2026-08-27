"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Drawer, DetailField, DrawerSection } from "@/components/common/drawer";
import { StatusBadge, exceptionReasonLabel } from "@/components/domain/status-badge";
import { TransactionDrawer } from "@/components/domain/transaction-drawer";
import { updateExceptionStatus, addExceptionNote } from "@/lib/api/exceptions";
import { formatDateTime } from "@/lib/format";

const STATUS_ACTIONS = [
  { value: "INVESTIGATING", label: "Start investigating" },
  { value: "RESOLVED", label: "Mark resolved" },
  { value: "DISMISSED", label: "Dismiss" },
  { value: "OPEN", label: "Reopen" },
];

/**
 * Reusable exception detail side panel (Exceptions screen and the
 * Reconciliation -> Exceptions tab).
 *
 * Shows the persisted exception fields plus its status actions and notes, and
 * exposes every linked transaction as a clickable row that opens the shared
 * TransactionDrawer. Nothing here recomputes the exception — it renders from
 * the backend payload and refreshes through the parent's list loader.
 */
export function ExceptionDetailDrawer({
  exception,
  onClose,
  onStatusChange,
  onNoteAdded,
}) {
  const [noteText, setNoteText] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(null);
  const [openTransactionId, setOpenTransactionId] = useState(null);

  if (!exception) return null;

  async function handleAddNote() {
    const text = noteText.trim();
    if (!text) return;
    setSavingNote(true);
    try {
      await addExceptionNote(exception.id, text);
      setNoteText("");
      await onNoteAdded?.();
    } catch {
      // Keep the user's text; do not clear on failure.
    } finally {
      setSavingNote(false);
    }
  }

  async function handleStatusChange(status) {
    setUpdatingStatus(status);
    try {
      await updateExceptionStatus(exception.id, status);
      await onStatusChange?.(status);
    } catch {
      // Error handled by keeping the previous state.
    } finally {
      setUpdatingStatus(null);
    }
  }

  return (
    <Drawer open={Boolean(exception)} onClose={onClose} label="Exception detail">
      <div className="divide-y divide-border">
        <DrawerSection>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
            <div className="col-span-2 flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-foreground">
                {exceptionReasonLabel(exception.reasonCode)}
              </span>
              <StatusBadge kind="exception" value={exception.status} />
            </div>
            <div className="col-span-2">
              <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Engine detail</dt>
              <dd className="mt-0.5 text-sm leading-relaxed text-muted-foreground">{exception.detail || "—"}</dd>
            </div>
            {exception.assignedTo && (
              <DetailField label="Assigned to">
                <span className="font-mono text-xs">{exception.assignedTo}</span>
              </DetailField>
            )}
            <DetailField label="Detected">{formatDateTime(exception.createdAt)}</DetailField>
          </dl>
        </DrawerSection>

        {exception.transactionIds?.length > 0 && (
          <DrawerSection title="Linked records">
            <ul role="list" className="space-y-2">
              {exception.transactionIds.map((id) => (
                <li key={id}>
                  <button
                    type="button"
                    onClick={() => setOpenTransactionId(id)}
                    className="block w-full truncate rounded-md bg-muted px-3 py-2 text-left font-mono text-xs text-foreground outline-none hover:bg-muted/70 focus-visible:ring-2 focus-visible:ring-ring/50 rounded-md"
                  >
                    {id}
                    <span className="sr-only"> — open transaction details</span>
                  </button>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-muted-foreground">
              Select a record to open its full transaction details.
            </p>
          </DrawerSection>
        )}

        <DrawerSection title="Actions">
          <div className="flex flex-wrap gap-2">
            {STATUS_ACTIONS.filter((a) => a.value !== exception.status).map((action) => (
              <Button
                key={action.value}
                variant="outline"
                size="sm"
                disabled={updatingStatus !== null}
                onClick={() => handleStatusChange(action.value)}
              >
                {updatingStatus === action.value ? "Saving..." : action.label}
              </Button>
            ))}
          </div>
        </DrawerSection>

        <DrawerSection title="Investigation notes">
          {exception.notes && exception.notes.length > 0 && (
            <ul role="list" className="mb-4 space-y-3">
              {exception.notes.map((note, idx) => (
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
            <textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder="Add a note..."
              rows={2}
              className="flex-1 resize-y rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none focus:ring-2 focus:ring-ring/50"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleAddNote();
                }
              }}
            />
            <Button
              size="sm"
              variant="outline"
              disabled={savingNote || !noteText.trim()}
              onClick={handleAddNote}
            >
              {savingNote ? "Adding..." : "Add"}
            </Button>
          </div>
        </DrawerSection>
      </div>

      <TransactionDrawer
        transactionId={openTransactionId}
        onClose={() => setOpenTransactionId(null)}
      />
    </Drawer>
  );
}
